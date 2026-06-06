#!/usr/bin/env python3
from __future__ import annotations

from tools.wetlab_target_render_utils import write_artifact

DEFAULT_OUT_MD = 'runs/wetlab_lrrk2_novelty_fill_map_current.md'


def build_payload() -> dict:
    rows = [
        {
            'target_id': 'LRRK2',
            'rank': 1,
            'novelty_compound_name': 'MLi-2',
            'series_class': 'benchmark_lrrk2_tool_compound',
            'selection_role': 'benchmark_control',
            'why_selected': 'Canonical LRRK2 benchmark inhibitor used to anchor biochemical and cellular pRab10 interpretation.',
        },
        {
            'target_id': 'LRRK2',
            'rank': 2,
            'novelty_compound_name': 'PFE-360',
            'series_class': 'benchmark_lrrk2_tool_compound',
            'selection_role': 'benchmark_control',
            'why_selected': 'Established LRRK2 inhibitor comparator that keeps the novelty lane tied to published kinase benchmarks.',
        },
        {
            'target_id': 'LRRK2',
            'rank': 3,
            'novelty_compound_name': 'BIIB122 (DNL151)',
            'series_class': 'clinical_lrrk2_benchmark',
            'selection_role': 'proceed_now',
            'why_selected': 'Clinical-stage LRRK2 benchmark used to connect the packet to a translational Parkinson-focused rail.',
        },
    ]
    return {
        'summary': {
            'status': 'wetlab_lrrk2_novelty_fill_map_ready',
            'target_id': 'LRRK2',
            'row_count': len(rows),
            'filled_slot_count': len(rows),
            'selection_policy': 'published_lrrk2_benchmark_and_translational_lane',
            'next_required_step': 'Use these benchmark and translational compounds as the novelty lane for the fifth Wave 2 LRRK2 packet.',
        },
        'rows': rows,
    }


if __name__ == '__main__':
    write_artifact(DEFAULT_OUT_MD, 'LRRK2 Novelty Fill Map', build_payload())
