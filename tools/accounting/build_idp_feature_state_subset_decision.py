#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_HOLDOUT_SUMMARY_JSON = 'runs/idp_3bead_holdout_v7_literature_anchor_kfrgsasa_r1_summary.json'
DEFAULT_DISAGREEMENT_JSON = 'runs/idp_literature_anchor_kfrgsasa_disagreement_summary_current.json'
DEFAULT_FAILURE_JSON = 'runs/idp_tau_k18_subset_failure_analysis_current.json'
DEFAULT_FEATURE_MASK_COMPARISON_JSON = 'runs/idp_literature_anchor_feature_mask_comparison_current.json'
DEFAULT_OUT_JSON = 'runs/idp_feature_state_subset_decision_current.json'
DEFAULT_OUT_MD = 'runs/idp_feature_state_subset_decision_current.md'


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _read_json(path_like: str) -> dict[str, Any]:
    with _resolve(path_like).open('r', encoding='utf-8') as fh:
        return json.load(fh)


def build_payload(
    holdout: dict[str, Any],
    disagreement: dict[str, Any],
    failure: dict[str, Any],
    feature_mask_comparison: dict[str, Any] | None = None,
) -> dict[str, Any]:
    hs = dict(holdout or {})
    ds = dict((disagreement.get('overall', {}) if isinstance(disagreement.get('overall', {}), dict) else {}) or {})
    fs = dict((failure.get('summary', {}) if isinstance(failure.get('summary', {}), dict) else {}) or {})
    mask_cmp = dict(feature_mask_comparison or {})
    gate_changes = int(ds.get('would_have_changed_gate_count', 0) or 0)
    state_changes = int(ds.get('would_have_changed_state_count', 0) or 0)
    corrected_pass_folds = int(hs.get('corrected_pass_folds', 0) or 0)
    fold_count = int(hs.get('fold_count', 0) or 0)
    mask_decision = str(mask_cmp.get('decision', '') or '')
    default_feature_mask = 'all'
    decision = 'no_go_broader_promotion'
    rationale = 'Subset is not clean enough for broader promotion yet: gate changes stayed at zero, but corrected pass folds are below full pass because tau_k18 corrected path still fails.'
    next_required_step = 'Stabilize tau_k18 corrected path, then rerun the literature-anchor subset holdout before any broader promotion.'
    if gate_changes == 0 and corrected_pass_folds == fold_count:
        if mask_decision == 'prefer_rg_sasa_only':
            decision = 'go_literature_anchor_default_mask_promotion'
            default_feature_mask = 'rg_sasa_only'
            rationale = 'Literature-anchor subset stayed gate-safe, fully passed at 7/7, and the narrower rg_sasa_only mask preserved zero state/gate changes.'
            next_required_step = 'Adopt rg_sasa_only as the default literature-anchor IDP shadow mask, keep broader full-IDP promotion blocked, and revisit broader promotion only after provisional-anchor and corrected-path risks are reduced.'
        else:
            decision = 'go_literature_anchor_promotion_review'
            rationale = 'Subset stayed gate-safe and fully passed; promotion review can begin.'
            next_required_step = 'Review whether the current feature mask should become the default for literature-anchor IDP shadow runs while keeping broader full-IDP promotion blocked.'
    return {
        'summary': {
            'decision': decision,
            'literature_anchor_default_promotion': bool(decision == 'go_literature_anchor_default_mask_promotion'),
            'broader_full_idp_promotion': False,
            'default_feature_mask': default_feature_mask,
            'fold_count': fold_count,
            'corrected_pass_folds': corrected_pass_folds,
            'would_have_changed_state_count': state_changes,
            'would_have_changed_gate_count': gate_changes,
            'blocking_fold': fs.get('fold_name', 'tau_k18') if corrected_pass_folds < fold_count else '',
            'blocking_reason': fs.get('failure_interpretation', ''),
            'next_required_step': next_required_step,
            'rationale': rationale,
        }
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload['summary']
    lines = [
        '# IDP Feature-State Literature-Anchor Subset Decision',
        '',
        f"- decision: `{s['decision']}`",
        f"- literature_anchor_default_promotion: `{s['literature_anchor_default_promotion']}`",
        f"- broader_full_idp_promotion: `{s['broader_full_idp_promotion']}`",
        f"- default_feature_mask: `{s['default_feature_mask']}`",
        f"- fold_count: `{s['fold_count']}`",
        f"- corrected_pass_folds: `{s['corrected_pass_folds']}`",
        f"- would_have_changed_state_count: `{s['would_have_changed_state_count']}`",
        f"- would_have_changed_gate_count: `{s['would_have_changed_gate_count']}`",
        f"- blocking_fold: `{s['blocking_fold']}`",
        '',
        '## Rationale',
        '',
        f"- {s['rationale']}",
        f"- {s['blocking_reason']}",
        '',
        '## Next Step',
        '',
        f"- {s['next_required_step']}",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description='Build decision artifact for literature-anchor subset feature_state shadow.')
    ap.add_argument('--holdout-summary-json', default=DEFAULT_HOLDOUT_SUMMARY_JSON)
    ap.add_argument('--disagreement-json', default=DEFAULT_DISAGREEMENT_JSON)
    ap.add_argument('--failure-json', default=DEFAULT_FAILURE_JSON)
    ap.add_argument('--feature-mask-comparison-json', default=DEFAULT_FEATURE_MASK_COMPARISON_JSON)
    ap.add_argument('--out-json', default=DEFAULT_OUT_JSON)
    ap.add_argument('--out-md', default=DEFAULT_OUT_MD)
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _read_json(args.holdout_summary_json),
        _read_json(args.disagreement_json),
        _read_json(args.failure_json),
        _read_json(args.feature_mask_comparison_json),
    )
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    _write_markdown(out_md, payload)


if __name__ == '__main__':
    main()
