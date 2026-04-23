#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description='Audit a built bioRxiv external validation package.')
    ap.add_argument('--package-root', required=True)
    ap.add_argument('--out-json', default='')
    ap.add_argument('--out-md', default='')
    args = ap.parse_args()

    package_root = (ROOT / args.package_root).resolve() if not Path(args.package_root).is_absolute() else Path(args.package_root).resolve()
    manifest_json = package_root / 'package_manifest.json'
    if not manifest_json.exists():
        raise FileNotFoundError(manifest_json)

    manifest = _read_json(manifest_json)
    failures: list[str] = []

    expected_top = [
        'package_manifest.md',
        'package_checksums.json',
        'package_checksums.sha256',
        'claim_matrix.csv',
        'claim_matrix.md',
        'copied_file_inventory.csv',
        'copied_file_inventory.md',
        'failure_triage.json',
        'failure_triage.md',
        'reviewer_summary.md',
        'reviewer_index.html',
    ]
    for rel in expected_top:
        if not (package_root / rel).exists():
            failures.append(f'missing top-level file: {rel}')

    checksums_json = package_root / 'package_checksums.json'
    if checksums_json.exists():
        checksums = _read_json(checksums_json)
        for row in checksums.get('files', []):
            rel = row.get('path', '')
            sha = row.get('sha256', '')
            p = package_root / rel
            if not p.exists():
                failures.append(f'checksum file missing: {rel}')
                continue
            actual = _sha256(p)
            if sha and actual != sha:
                failures.append(f'checksum mismatch: {rel}')

    set_rows = manifest.get('sets', []) if isinstance(manifest.get('sets'), list) else []
    for row in set_rows:
        set_id = str(row.get('set_id', ''))
        for file_row in row.get('files', []) if isinstance(row.get('files'), list) else []:
            dst = Path(str(file_row.get('dst', '')))
            if not dst.exists():
                failures.append(f'set {set_id} missing copied artifact: {dst}')

    result = {
        'package_root': str(package_root),
        'pass': not failures,
        'failure_count': len(failures),
        'failures': failures,
    }

    out_json = Path(args.out_json) if args.out_json else package_root / 'audit.json'
    out_md = Path(args.out_md) if args.out_md else package_root / 'audit.md'
    out_json.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    out_md.write_text(
        '# Package Audit\n\n'
        + f"- pass: `{result['pass']}`\n"
        + f"- failure_count: `{result['failure_count']}`\n\n"
        + ('\n'.join(f'- {x}' for x in failures) + '\n' if failures else '- no failures\n'),
        encoding='utf-8',
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == '__main__':
    raise SystemExit(main())
