#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
OUT_JSON = ROOT / 'runs/cross_family_residual_shadow_layer_plan_current.json'
OUT_CSV = ROOT / 'runs/cross_family_residual_shadow_layer_plan_current.csv'
OUT_MD = ROOT / 'runs/cross_family_residual_shadow_layer_plan_current.md'


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text('', encoding='utf-8')
        return
    with path.open('w', encoding='utf-8', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def build_payload() -> dict[str, Any]:
    ca2_ready = _read_json(ROOT / 'runs/ca2_packet_replacement_readiness_current.json')
    pxr_ready = _read_json(ROOT / 'runs/pxr_packet_fill_readiness_current.json')
    ca2_ready_count = int(ca2_ready.get('summary', {}).get('ready_row_count', 0) or 0)
    ca2_blocked_count = int(ca2_ready.get('summary', {}).get('blocked_row_count', 0) or 0)
    pxr_ready_count = int(pxr_ready.get('summary', {}).get('ready_for_apply_row_count', 0) or 0)
    pxr_blocked_count = int(pxr_ready.get('summary', {}).get('blocked_row_count', 0) or 0)
    family_rows = [
        {
            'family': 'gpcr',
            'shadow_status': 'locked_decoy_shadow_validated',
            'primary_artifact': 'runs/gpcr_residual_mode_comparison_narrow_v2_current.md',
            'residual_mode': 'shadow_then_apply_equal_size_only',
            'kalman_mode': 'not_applicable',
            'next_runnable_step': 'Prototype cross-family router shell with GPCR family token carried through unchanged.',
        },
        {
            'family': 'ion_channel',
            'shadow_status': 'equal_size_shadow_scaffold_ready',
            'primary_artifact': 'runs/ion_kinase_residual_equal_size_shadow_current.md',
            'residual_mode': 'shadow_only_equal_size_next',
            'kalman_mode': 'not_applicable',
            'next_runnable_step': 'Run the equal-size ion shadow scaffold and confirm shadow-only telemetry preserves the active score before any locked-decoy follow-up.',
        },
        {
            'family': 'kinase',
            'shadow_status': 'equal_size_shadow_scaffold_ready',
            'primary_artifact': 'runs/ion_kinase_residual_equal_size_shadow_current.md',
            'residual_mode': 'shadow_only_equal_size_next',
            'kalman_mode': 'not_applicable',
            'next_runnable_step': 'Run the equal-size kinase shadow scaffold and keep active-score changes disabled until family-specific quality evidence exists.',
        },
        {
            'family': 'idp',
            'shadow_status': 'design_only_feature_state_path',
            'primary_artifact': 'runs/biorxiv_temporal_idp_remaining_policy_current.md',
            'residual_mode': 'shadow_only_no_rank_override',
            'kalman_mode': 'feature_state_smoothing_only',
            'next_runnable_step': 'Start Kalman smoothing on contact/min-distance/state posterior features only; no coordinate hallucination and no ranking override.',
        },
        {
            'family': 'non_kinase_enzyme_ca2',
            'shadow_status': 'core_binders_verified_workbook_promoted',
            'primary_artifact': 'runs/ca2_verified_binding_promotion_current.md',
            'residual_mode': 'shadow_only_after_core_packet_verified',
            'kalman_mode': 'not_applicable',
            'readiness_signal': f'ready_rows={ca2_ready_count}; blocked_rows={ca2_blocked_count}',
            'next_runnable_step': 'Use the now-ready CA2 core binder rows to unblock the core packet, then attach the CA2 family token to the global shadow shell.',
        },
        {
            'family': 'nuclear_receptor_pxr',
            'shadow_status': 'core_binders_verified_workbook_promoted',
            'primary_artifact': 'runs/pxr_verified_binding_promotion_current.md',
            'residual_mode': 'shadow_only_after_core_packet_verified',
            'kalman_mode': 'not_applicable',
            'readiness_signal': f'ready_rows={pxr_ready_count}; blocked_rows={pxr_blocked_count}',
            'next_runnable_step': 'Use the now-ready PXR core binder rows, preserve assay-type-aware provenance, and attach the PXR family token to the global shadow shell.',
        },
        {
            'family': 'transporter',
            'shadow_status': 'scaffold_only',
            'primary_artifact': 'docs/transporter_membrane_runnable_scaffold_notes.md',
            'residual_mode': 'shadow_shell_not_started',
            'kalman_mode': 'not_applicable',
            'readiness_signal': 'scaffold_only',
            'next_runnable_step': 'Finish AQP1/GLUT1 runnable packet scaffolds before adding the transporter family token to the cross-family shadow shell.',
        },
    ]
    for row in family_rows:
        row.setdefault('readiness_signal', row['shadow_status'])
    return {
        'summary': {
            'goal': 'cross_family_residual_shadow_layer',
            'mode': 'shadow_only_first',
            'family_count': len(family_rows),
            'next_required_step': 'Run the ion/kinase equal-size shadow scaffold first, then use authoritative CA2/PXR binder rows to unblock additional family tokens before any cross-family apply-mode promotion.',
            'global_outputs': [
                'baseline_score',
                'shadow_delta',
                'shadow_corrected_score',
                'router_uncertainty',
                'family_token',
                'abstain_reason',
            ],
            'global_guardrails': [
                'shadow_only_until_family_equal_size_pass',
                'family-aware abstention',
                'no_idp_coordinate_hallucination',
                'no_100k_router_promotion_without_quality_gain',
            ],
        },
        'family_rows': family_rows,
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        '# Cross-Family Residual Shadow Layer Plan',
        '',
        f"- mode: `{payload['summary']['mode']}`",
        f"- family_count: `{payload['summary']['family_count']}`",
        '',
        '## Next Step',
        '',
        f"- {payload['summary']['next_required_step']}",
        '',
        '## Global Outputs',
        '',
    ]
    for item in payload['summary']['global_outputs']:
        lines.append(f'- `{item}`')
    lines.extend(['', '## Global Guardrails', ''])
    for item in payload['summary']['global_guardrails']:
        lines.append(f'- `{item}`')
    lines.extend(['', '## Family Rollout', '', '| family | shadow_status | residual_mode | kalman_mode | readiness_signal | next_runnable_step |', '| --- | --- | --- | --- | --- | --- |'])
    for row in payload['family_rows']:
        lines.append(f"| {row['family']} | {row['shadow_status']} | {row['residual_mode']} | {row['kalman_mode']} | `{row['readiness_signal']}` | {row['next_runnable_step']} |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main() -> None:
    payload = build_payload()
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    _write_csv(OUT_CSV, payload['family_rows'])
    _write_markdown(OUT_MD, payload)


if __name__ == '__main__':
    main()
