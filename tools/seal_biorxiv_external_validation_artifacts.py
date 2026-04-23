#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description="Create a SHA256 seal manifest over current bioRxiv external-validation artifacts.")
    ap.add_argument("--current-package-meta-json", default="runs/biorxiv_external_validation_package_current.json")
    ap.add_argument("--run-summary-json", default="runs/external_validation_blind_runs/external_validation_blind_runs_2026-03-22_biorxiv_v7r1/summary.json")
    ap.add_argument("--claim-matrix-md", default="runs/biorxiv_external_validation_claim_matrix_current.md")
    ap.add_argument("--audit-json", default="runs/biorxiv_external_validation_audit_current.json")
    ap.add_argument("--main-table-md", default="runs/biorxiv_external_validation_main_table_current.md")
    ap.add_argument("--temporal-baseline-md", default="runs/biorxiv_temporal_submission_baseline_current.md")
    ap.add_argument("--submission-assets-zip", default="runs/biorxiv_submission_assets_current.zip")
    ap.add_argument("--out-json", default="runs/biorxiv_external_validation_governance_seal_current.json")
    ap.add_argument("--out-md", default="runs/biorxiv_external_validation_governance_seal_current.md")
    args = ap.parse_args()

    meta = _read_json((ROOT / args.current_package_meta_json).resolve())
    current_files = meta.get("current_files", {}) if isinstance(meta.get("current_files"), dict) else {}
    package_zip = Path(current_files.get("archive_zip", str((ROOT / "runs/biorxiv_external_validation_package_current.zip").resolve()))).resolve()
    reviewer_index = Path(current_files.get("reviewer_index_html", str((ROOT / "runs/biorxiv_external_validation_reviewer_index_current.html").resolve()))).resolve()

    files = [
        ("package_zip", package_zip),
        ("reviewer_index_html", reviewer_index),
        ("run_summary_json", (ROOT / args.run_summary_json).resolve()),
        ("claim_matrix_md", (ROOT / args.claim_matrix_md).resolve()),
        ("audit_json", (ROOT / args.audit_json).resolve()),
        ("main_table_md", (ROOT / args.main_table_md).resolve()),
        ("temporal_baseline_md", (ROOT / args.temporal_baseline_md).resolve()),
        ("submission_assets_zip", (ROOT / args.submission_assets_zip).resolve()),
    ]

    sealed: list[dict[str, Any]] = []
    for label, path in files:
        if not path.exists():
            continue
        sealed.append(
            {
                "label": label,
                "path": str(path),
                "size_bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )

    payload = {
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "seal_mode": "sha256_manifest",
        "sealed_file_count": len(sealed),
        "files": sealed,
    }
    out_json = (ROOT / args.out_json).resolve()
    out_md = (ROOT / args.out_md).resolve()
    _write_json(out_json, payload)

    md_lines = [
        "# bioRxiv External Validation Governance Seal",
        "",
        f"- seal_mode: `{payload['seal_mode']}`",
        f"- sealed_file_count: `{payload['sealed_file_count']}`",
        "",
        "| label | size_bytes | sha256 |",
        "| --- | ---: | --- |",
    ]
    for row in sealed:
        md_lines.append(f"| {row['label']} | {row['size_bytes']} | `{row['sha256']}` |")
    _write_text(out_md, "\n".join(md_lines) + "\n")

    print(json.dumps({"ok": True, "out_json": str(out_json), "sealed_file_count": len(sealed)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
