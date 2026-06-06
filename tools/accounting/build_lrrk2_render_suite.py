#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, payload_summary, rows_by_target, write_artifact

DEFAULT_PORTFOLIO_JSON = 'runs/wetlab_partner_target_portfolio_current.json'
DEFAULT_VALIDATION_JSON = 'runs/wetlab_validation_companion_panels_current.json'
DEFAULT_REPURPOSING_FILL_JSON = 'runs/wetlab_lrrk2_repurposing_fill_map_current.json'
DEFAULT_NOVELTY_FILL_JSON = 'runs/wetlab_lrrk2_novelty_fill_map_current.json'
DEFAULT_SUITE_MD = 'runs/lrrk2_render_suite_current.md'
DEFAULT_CONDITION_CARD_MD = 'runs/lrrk2_condition_card_current.md'
DEFAULT_PANEL_MD = 'runs/lrrk2_selectivity_panel_current.md'
DEFAULT_ASSAY_MD = 'runs/lrrk2_assay_packet_current.md'
DEFAULT_GONOGO_MD = 'runs/lrrk2_go_no_go_card_current.md'
DEFAULT_EXPORT_MD = 'runs/lrrk2_mjff_export_current.md'
TARGET_ID = 'LRRK2'


def build_payload(portfolio_payload: dict[str, Any], validation_payload: dict[str, Any], repurposing_fill_payload: dict[str, Any] | None = None, novelty_fill_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    portfolio_row = rows_by_target(portfolio_payload)[TARGET_ID]
    validation_row = rows_by_target(validation_payload)[TARGET_ID]
    rep_rows = [dict(row) for row in ((repurposing_fill_payload or {}).get('rows', []) or []) if str(row.get('target_id', '')).strip() == TARGET_ID]
    nov_rows = [dict(row) for row in ((novelty_fill_payload or {}).get('rows', []) or []) if str(row.get('target_id', '')).strip() == TARGET_ID]
    rep_controls = '; '.join(str(row.get('compound_name', '')).strip() for row in rep_rows if str(row.get('compound_name', '')).strip())
    nov_controls = '; '.join(str(row.get('novelty_compound_name', '')).strip() for row in nov_rows if str(row.get('novelty_compound_name', '')).strip())
    content_ready = len(rep_rows) >= 3 and len(nov_rows) >= 3

    condition_card = {
        'summary': payload_summary('lrrk2_condition_card_ready', TARGET_ID, 'condition_card', 4, 'Use this card as the fixed LRRK2 assay context before interpreting any Parkinson translational claim.'),
        'structured': {
            'target_id': TARGET_ID,
            'partner_track_id': 'MJFF_LRRK2',
            'primary_biochemical_arm': 'recombinant LRRK2 kinase enzymatic inhibition arm with simple target-engagement framing',
            'cellular_arm': 'cellular pRab10 orthogonal replay after biochemical survivors are cleaned',
            'cns_liability_panel': validation_row['primary_companion_panel'],
            'first_go_no_go': 'promote only rows that keep LRRK2 biochemical signal while surviving kinase selectivity and CNS-relevant sanity checks',
            'repurposing_controls': rep_controls or 'pending_wave2_compound_fill',
            'novelty_controls': nov_controls or 'pending_wave2_compound_fill',
            'content_ready': content_ready,
            'source_anchor': portfolio_row['source_anchor'],
            'source_url': portfolio_row['source_url'],
        },
        'rows': [
            {'condition_name': 'primary_lrrk2_biochemical_arm', 'value': 'recombinant LRRK2 kinase assay', 'why': 'keeps the first packet target-led before cellular Parkinson context expands', 'source_anchor': portfolio_row['source_anchor']},
            {'condition_name': 'kinase_selectivity', 'value': validation_row['primary_companion_panel'], 'why': 'large flexible kinases need selectivity and liability cleanup early', 'source_anchor': validation_row['companion_why']},
            {'condition_name': 'cellular_prab10_replay', 'value': 'clean subset only', 'why': 'prevents biochemical-only or cell-only carryover from driving interpretation', 'source_anchor': portfolio_row['primary_strength']},
            {'condition_name': 'first_packet_scope', 'value': 'kinase-first LRRK2 packet before broader Parkinson framing', 'why': 'keeps the ask tractable for a translational MJFF-style rail', 'source_anchor': portfolio_row['main_risk']},
        ],
    }

    selectivity_panel = {
        'summary': payload_summary('lrrk2_selectivity_panel_ready', TARGET_ID, 'selectivity_panel', 4, 'Run this kinase-selectivity and CNS-liability panel in the first packet so large-kinase carryover does not outrun LRRK2 evidence.'),
        'structured': {
            'target_id': TARGET_ID,
            'panel_label': validation_row['primary_companion_panel'],
            'panel_rationale': validation_row['companion_why'],
            'classification_rule': 'promote only rows that retain LRRK2 biochemical and cellular signal while staying clean on kinase/CNS sanity checks',
            'outbound_rule': validation_row['outbound_rule'],
        },
        'rows': [
            {'step_rank': '1', 'step_label': 'lrrk2_primary', 'plan': 'measure LRRK2 inhibition in the primary biochemical arm first', 'source_anchor': portfolio_row['source_anchor']},
            {'step_rank': '2', 'step_label': 'kinase_selectivity', 'plan': 'use kinase selectivity and CNS-relevant sanity checks before treating any row as actionable', 'source_anchor': validation_row['companion_why']},
            {'step_rank': '3', 'step_label': 'cellular_prab10_replay', 'plan': 'replay only the clean subset in a bounded cellular pRab10 orthogonal arm', 'source_anchor': portfolio_row['primary_strength']},
            {'step_rank': '4', 'step_label': 'parkinson_context', 'plan': 'contextualize clean rows against translational Parkinson constraints instead of treating them as de-risked leads', 'source_anchor': portfolio_row['main_risk']},
        ],
    }

    assay_packet = {
        'summary': payload_summary('lrrk2_assay_packet_ready', TARGET_ID, 'assay_packet', 4, 'Use this packet as the executable first-pass assay stack for the LRRK2 translational rail.'),
        'structured': {
            'target_id': TARGET_ID,
            'first_assay': 'recombinant LRRK2 biochemical inhibition assay followed by cellular pRab10 orthogonal replay',
            'first_packet_goal': 'determine whether the shortlist contains genuine LRRK2-biased signal rather than generic kinase carryover',
            'buffer_program': 'primary LRRK2 biochemical arm plus kinase-selectivity/CNS sanity and cellular pRab10 orthogonal replay',
            'companion_panel': validation_row['primary_companion_panel'],
            'offer_model': 'serialized_wave2_after_final2',
        },
        'rows': [
            {'step_rank': '1', 'step_label': 'primary_biochemical_assay', 'assay': 'run a bounded recombinant LRRK2 inhibition assay first', 'source_anchor': portfolio_row['source_anchor']},
            {'step_rank': '2', 'step_label': 'kinase_selectivity_sanity', 'assay': 'apply kinase selectivity and CNS-relevant sanity checks before external interpretation', 'source_anchor': validation_row['companion_why']},
            {'step_rank': '3', 'step_label': 'cellular_prab10_replay', 'assay': 'retest survivors in a bounded cellular pRab10 orthogonal replay', 'source_anchor': portfolio_row['primary_strength']},
            {'step_rank': '4', 'step_label': 'optional_followup', 'assay': 'open broader Parkinson follow-up only for rows that stay clean across biochemical and cellular replay', 'source_anchor': portfolio_row['main_risk']},
        ],
    }

    go_no_go = {
        'summary': payload_summary('lrrk2_go_no_go_card_ready', TARGET_ID, 'go_no_go_card', 4, 'Use this card to separate genuine LRRK2 progression from broad kinase or CNS-liability background signal.'),
        'structured': {
            'target_id': TARGET_ID,
            'primary_promote_rule': 'LRRK2 biochemical signal survives kinase selectivity/CNS sanity and cellular pRab10 replay',
            'dual_bucket_rule': 'signal appears real in both biochemical and cellular arms but still needs bounded chemistry follow-up',
            'reject_rule': 'biochemical signal collapses under kinase selectivity, CNS liability, or cellular replay',
            'headline': 'LRRK2 packet built to keep translational Parkinson context subordinate to direct target evidence.',
        },
        'rows': [
            {'decision_case': 'promote_clean_lrrk2_biochemical_bias', 'decision_rule': 'LRRK2 signal remains while kinase selectivity and cellular replay stay favorable', 'action': 'promote to bounded Wave 2 follow-up'},
            {'decision_case': 'hold_cellular_biochemical_split', 'decision_rule': 'signal is present but biochemical and cellular interpretations diverge', 'action': 'hold for bounded clarification'},
            {'decision_case': 'reject_kinase_or_cns_carryover', 'decision_rule': 'signal carries into kinase/CNS sanity panels without a clean LRRK2-biased profile', 'action': 'reject as non-specific carryover'},
            {'decision_case': 'reject_noisy_translational_context', 'decision_rule': 'signal only survives as broad translational noise rather than target-led evidence', 'action': 'reject as non-decision-grade'},
        ],
    }

    export_payload = {
        'summary': payload_summary('lrrk2_mjff_export_ready', TARGET_ID, 'partner_export', 4, 'Use this export only after the LRRK2 compound lanes are filled and the first-pass packet is no longer content-blocked.'),
        'structured': {
            'target_id': TARGET_ID,
            'partner_track_id': 'MJFF_LRRK2',
            'partner_track_label': 'MJFF translational Parkinson\'s rail',
            'email_subject': 'LRRK2 micro-validation packet with bounded biochemical and cellular pRab10 replay',
            'proposal_title': 'LRRK2 biochemical-first micro-validation packet',
            'proposal_summary': 'A Wave 2 packet that asks one narrow question: does the shortlist contain LRRK2-biased signal that survives kinase-selectivity/CNS sanity checks and a bounded cellular pRab10 replay?',
            'email_opening_angle': 'Lead with LRRK2 as a bounded biochemical-to-cellular triage problem, not as a fully de-risked Parkinson program.',
        },
        'rows': [
            {'attachment_rank': '1', 'artifact': DEFAULT_CONDITION_CARD_MD, 'why': 'fixes the LRRK2 assay context before interpretation'},
            {'attachment_rank': '2', 'artifact': DEFAULT_PANEL_MD, 'why': 'shows kinase/CNS cleanup is day-one work'},
            {'attachment_rank': '3', 'artifact': DEFAULT_ASSAY_MD, 'why': 'gives a bounded executable LRRK2 assay stack'},
            {'attachment_rank': '4', 'artifact': DEFAULT_GONOGO_MD, 'why': 'keeps biochemical-versus-cellular outcomes explicit'},
        ],
    }

    suite_rows = [
        {'artifact_kind': 'condition_card', 'artifact_path': DEFAULT_CONDITION_CARD_MD, 'status': condition_card['summary']['status']},
        {'artifact_kind': 'selectivity_panel', 'artifact_path': DEFAULT_PANEL_MD, 'status': selectivity_panel['summary']['status']},
        {'artifact_kind': 'assay_packet', 'artifact_path': DEFAULT_ASSAY_MD, 'status': assay_packet['summary']['status']},
        {'artifact_kind': 'go_no_go_card', 'artifact_path': DEFAULT_GONOGO_MD, 'status': go_no_go['summary']['status']},
        {'artifact_kind': 'partner_export', 'artifact_path': DEFAULT_EXPORT_MD, 'status': export_payload['summary']['status']},
    ]

    return {
        'summary': {
            'status': 'lrrk2_render_suite_ready',
            'target_id': TARGET_ID,
            'artifact_count': len(suite_rows),
            'partner_track_id': 'MJFF_LRRK2',
            'repurposing_filled_slot_count': len(rep_rows),
            'novelty_filled_slot_count': len(nov_rows),
            'content_ready': content_ready,
            'next_required_step': 'Use the generated LRRK2 packet set as the fifth live Wave 2 target overlay once T. cruzi KRS1 resolves.' if content_ready else 'Use the generated LRRK2 packet set as the fifth Wave 2 target overlay once T. cruzi KRS1 resolves and compound fill is real.',
        },
        'artifacts': {
            'condition_card': condition_card,
            'selectivity_panel': selectivity_panel,
            'assay_packet': assay_packet,
            'go_no_go_card': go_no_go,
            'partner_export': export_payload,
        },
        'rows': suite_rows,
    }


def _write_suite(payload: dict[str, Any]) -> None:
    write_artifact(DEFAULT_SUITE_MD, 'LRRK2 Render Suite', {'summary': payload['summary'], 'structured': {'target_id': payload['summary']['target_id'], 'partner_track_id': payload['summary']['partner_track_id']}, 'rows': payload['rows']})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Build the LRRK2 target-specific Wave 2 overlay packet set.')
    parser.add_argument('--portfolio-json', default=DEFAULT_PORTFOLIO_JSON)
    parser.add_argument('--validation-json', default=DEFAULT_VALIDATION_JSON)
    parser.add_argument('--repurposing-fill-json', default=DEFAULT_REPURPOSING_FILL_JSON)
    parser.add_argument('--novelty-fill-json', default=DEFAULT_NOVELTY_FILL_JSON)
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    payload = build_payload(load_json(args.portfolio_json), load_json(args.validation_json), load_json(args.repurposing_fill_json), load_json(args.novelty_fill_json))
    write_artifact(DEFAULT_CONDITION_CARD_MD, 'LRRK2 Condition Card', payload['artifacts']['condition_card'])
    write_artifact(DEFAULT_PANEL_MD, 'LRRK2 Selectivity Panel', payload['artifacts']['selectivity_panel'])
    write_artifact(DEFAULT_ASSAY_MD, 'LRRK2 Assay Packet', payload['artifacts']['assay_packet'])
    write_artifact(DEFAULT_GONOGO_MD, 'LRRK2 Go / No-Go Card', payload['artifacts']['go_no_go_card'])
    write_artifact(DEFAULT_EXPORT_MD, 'LRRK2 MJFF Export', payload['artifacts']['partner_export'])
    _write_suite(payload)
