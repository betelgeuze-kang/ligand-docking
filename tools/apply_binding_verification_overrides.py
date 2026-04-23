#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

FAMILY_DEFAULTS: dict[str, dict[str, str]] = {
    'ca2': {
        'sheet_csv': 'runs/ca2_binding_verification_sheet_current.csv',
        'sheet_json': 'runs/ca2_binding_verification_sheet_current.json',
        'sheet_md': 'runs/ca2_binding_verification_sheet_current.md',
        'overrides_json': 'runs/ca2_binding_verification_overrides_current.json',
        'title': 'CA2 Binding Verification Sheet',
    },
    'pxr': {
        'sheet_csv': 'runs/pxr_binding_verification_sheet_current.csv',
        'sheet_json': 'runs/pxr_binding_verification_sheet_current.json',
        'sheet_md': 'runs/pxr_binding_verification_sheet_current.md',
        'overrides_json': 'runs/pxr_binding_verification_overrides_current.json',
        'title': 'PXR Binding Verification Sheet',
    },
}


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open('r', encoding='utf-8', newline='') as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text('', encoding='utf-8')
        return
    with path.open('w', encoding='utf-8', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_markdown(path: Path, payload: dict[str, Any], title: str) -> None:
    lines = [
        f'# {title}',
        '',
        f"- row_count: `{payload['summary']['row_count']}`",
        f"- verified_row_count: `{payload['summary']['verified_row_count']}`",
        f"- verified_binder_row_count: `{payload['summary']['verified_binder_row_count']}`",
        f"- pending_row_count: `{payload['summary']['pending_row_count']}`",
        '',
        '## Verification Rows',
        '',
        '| priority_rank | packet_step | replacement_ligand_id | binder | verify_reference_binding_kcal_mol | verify_provenance_source | verify_source_url | verification_status |',
        '| ---: | --- | --- | --- | --- | --- | --- | --- |',
    ]
    for row in payload['sheet_rows']:
        lines.append(
            f"| {row['priority_rank']} | {row['packet_step']} | `{row['replacement_ligand_id']}` | {row['replacement_is_binder']} | {row['verify_reference_binding_kcal_mol']} | `{row['verify_provenance_source']}` | `{row['verify_source_url']}` | `{row['verification_status']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def build_payload(sheet_rows: list[dict[str, str]], overrides: list[dict[str, str]], family: str) -> dict[str, Any]:
    overrides_by_step = {str(row['packet_step']).strip(): row for row in overrides}
    updated: list[dict[str, Any]] = []
    verified = 0
    verified_binders = 0
    for row in sheet_rows:
        out = dict(row)
        step = str(row.get('packet_step', '')).strip()
        ov = overrides_by_step.get(step)
        if ov:
            out['verify_reference_binding_kcal_mol'] = str(ov.get('verify_reference_binding_kcal_mol', '')).strip()
            out['verify_provenance_source'] = str(ov.get('verify_provenance_source', '')).strip()
            out['verify_source_url'] = str(ov.get('verify_source_url', '')).strip()
            out['verification_status'] = str(ov.get('verification_status', '')).strip() or 'verified_activity_reference'
            note_bits = [str(out.get('notes', '')).strip(), str(ov.get('notes_append', '')).strip()]
            out['notes'] = ' '.join(bit for bit in note_bits if bit).strip()
        is_verified = bool(str(out.get('verify_reference_binding_kcal_mol', '')).strip() and str(out.get('verify_provenance_source', '')).strip() and str(out.get('verify_source_url', '')).strip())
        if is_verified:
            verified += 1
            if str(out.get('replacement_is_binder', '')).strip() == '1':
                verified_binders += 1
        elif not str(out.get('verification_status', '')).strip():
            out['verification_status'] = 'pending_binding_provenance_review'
        updated.append(out)
    return {
        'summary': {
            'family': family,
            'row_count': len(updated),
            'verified_row_count': verified,
            'verified_binder_row_count': verified_binders,
            'pending_row_count': len(updated) - verified,
            'next_required_step': 'Copy verified binder values into authoritative packet workbooks after manual spot-check, then continue remaining binder/non-binder evidence.'
        },
        'sheet_rows': updated,
        'overrides_applied': len(overrides),
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description='Apply verified binding/provenance overrides to a family verification sheet.')
    p.add_argument('--family', choices=sorted(FAMILY_DEFAULTS), required=True)
    p.add_argument('--sheet-csv')
    p.add_argument('--sheet-json')
    p.add_argument('--sheet-md')
    p.add_argument('--overrides-json')
    args = p.parse_args()
    defaults = FAMILY_DEFAULTS[args.family]
    for key in ('sheet_csv','sheet_json','sheet_md','overrides_json'):
        if not getattr(args, key):
            setattr(args, key, defaults[key])
    return args


def main() -> None:
    args = parse_args()
    sheet_rows = _read_csv(_resolve(args.sheet_csv))
    overrides = json.loads(_resolve(args.overrides_json).read_text(encoding='utf-8'))['overrides']
    payload = build_payload(sheet_rows, overrides, args.family)
    _write_csv(_resolve(args.sheet_csv), payload['sheet_rows'])
    _resolve(args.sheet_json).write_text(json.dumps(payload, indent=2), encoding='utf-8')
    _write_markdown(_resolve(args.sheet_md), payload, FAMILY_DEFAULTS[args.family]['title'])


if __name__ == '__main__':
    main()
