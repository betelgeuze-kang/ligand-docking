#!/usr/bin/env python3
from __future__ import annotations

import argparse
from tools.wetlab_target_render_utils import materialize_repurposing_rows, maybe_load_json, write_artifact

DEFAULT_OUT_MD = 'runs/wetlab_lrrk2_repurposing_fill_map_current.md'
DEFAULT_BROAD_SCREEN_AUTOFILL_JSON = "runs/wetlab_broad_screen_repurposing_autofill_current.json"


def build_payload(broad_screen_autofill: dict | None = None) -> dict:
    manual_rows = [
        {
            'target_id': 'LRRK2',
            'rank': 1,
            'slot_rank': 1,
            'compound_name': 'Crizotinib',
            'source_class': 'approved_multikinase_comparator',
            'first_contact_use_mode': 'comparator_only',
            'selection_role': 'comparator_only',
            'why_selected': 'Approved kinase drug kept as a low-friction comparator for translational LRRK2 triage rather than a direct benchmark claim.',
        },
        {
            'target_id': 'LRRK2',
            'rank': 2,
            'slot_rank': 2,
            'compound_name': 'Sunitinib',
            'source_class': 'approved_multikinase_comparator',
            'first_contact_use_mode': 'comparator_only',
            'selection_role': 'comparator_only',
            'why_selected': 'Approved kinase-active comparator that helps bound broad kinase carryover before a Parkinson-focused interpretation.',
        },
        {
            'target_id': 'LRRK2',
            'rank': 3,
            'slot_rank': 3,
            'compound_name': 'Nilotinib',
            'source_class': 'approved_cns_adjacent_kinase_comparator',
            'first_contact_use_mode': 'comparator_only',
            'selection_role': 'comparator_only',
            'why_selected': 'Approved CNS-adjacent kinase comparator used to keep the packet grounded in purchasable compounds while selectivity is still primary.',
        },
    ]
    for idx, row in enumerate(manual_rows, start=1):
        row.setdefault("priority_rank", 12)
        row.setdefault("outreach_track_id", "MJFF_LRRK2")
        row.setdefault("brief_slot_name", f"repurposing_{idx}")
        row.setdefault("seed_status", row.get("source_class", "approved_comparator"))
        row.setdefault("vendor_check_required", False)
        row.setdefault("cost_check_required", False)
        row.setdefault("selectivity_note", "Approved kinase comparator row used to keep the first LRRK2 packet bounded before any disease-facing interpretation.")
        row.setdefault("usage_rationale", row.get("why_selected", "Approved comparator kept for a low-friction LRRK2 translational lane."))
        row.setdefault("must_not_do", "Do not treat this comparator row as proof of Parkinson-focused LRRK2 selectivity.")
        row.setdefault("source_anchor", "lrrk2_manual_repuposing_lane")
        row.setdefault("source_url", "runs/wetlab_lrrk2_repurposing_fill_map_current.md")
    rows, bulk_override_applied = materialize_repurposing_rows(
        target_id="LRRK2",
        manual_rows=manual_rows,
        bulk_autofill_payload=broad_screen_autofill,
        target_brief_artifact="runs/lrrk2_render_suite_current.md",
        first_contact_packet_artifact="runs/lrrk2_launch_packet_current.md",
        track_label="MJFF translational Parkinson's rail",
        default_outreach_track_id="MJFF_LRRK2",
    )
    return {
        'summary': {
            'status': 'wetlab_lrrk2_repurposing_fill_map_ready',
            'target_id': 'LRRK2',
            'row_count': len(rows),
            'filled_slot_count': len(rows),
            'bulk_override_applied': bulk_override_applied,
            'selection_policy': 'approved_or_easy_procurement_kinase_comparator_lane',
            'next_required_step': 'Use these approved kinase comparators as the repurposing lane for the fifth Wave 2 LRRK2 packet.',
        },
        'rows': rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the LRRK2 repurposing fill map.")
    parser.add_argument("--broad-screen-autofill-json", default=DEFAULT_BROAD_SCREEN_AUTOFILL_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    write_artifact(
        args.out_md,
        'LRRK2 Repurposing Fill Map',
        build_payload(maybe_load_json(args.broad_screen_autofill_json)),
    )
