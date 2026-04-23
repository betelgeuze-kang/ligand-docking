#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
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


def _record(label: str, path: Path) -> dict[str, Any]:
    return {
        "label": label,
        "path": str(path.resolve()),
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _resolve_run_path(path_str: str) -> Path:
    p = Path(path_str)
    return p.resolve() if p.is_absolute() else (ROOT / p).resolve()


def main() -> int:
    ap = argparse.ArgumentParser(description="Freeze the current bioRxiv submission bundle into an immutable baseline manifest.")
    ap.add_argument("--current-package-meta-json", default="runs/biorxiv_external_validation_package_current.json")
    ap.add_argument("--submission-assets-zip", default="runs/biorxiv_submission_assets_current.zip")
    ap.add_argument("--submission-assets-manifest-json", default="runs/biorxiv_submission_assets_current/submission_assets_manifest.json")
    ap.add_argument("--temporal-baseline-json", default="runs/biorxiv_temporal_submission_baseline_current.json")
    ap.add_argument("--robustness-matrix-json", default="runs/biorxiv_robustness_matrix_current.json")
    ap.add_argument("--robustness-comparison-json", default="runs/biorxiv_robustness_comparison_summary_current.json")
    ap.add_argument("--governance-seal-json", default="runs/biorxiv_external_validation_governance_seal_current.json")
    ap.add_argument("--archive-zip", default="")
    ap.add_argument("--out-json", default="runs/biorxiv_submission_freeze_current.json")
    ap.add_argument("--out-md", default="runs/biorxiv_submission_freeze_current.md")
    args = ap.parse_args()

    meta_path = _resolve_run_path(args.current_package_meta_json)
    submission_zip = _resolve_run_path(args.submission_assets_zip)
    submission_manifest = _resolve_run_path(args.submission_assets_manifest_json)
    temporal_json = _resolve_run_path(args.temporal_baseline_json)
    robustness_matrix_json = _resolve_run_path(args.robustness_matrix_json)
    robustness_compare_json = _resolve_run_path(args.robustness_comparison_json)
    governance_seal_json = _resolve_run_path(args.governance_seal_json)

    meta = _read_json(meta_path)
    bundle_tag = str(meta.get("bundle_tag") or "unknown_bundle").strip() or "unknown_bundle"
    archive_zip = (
        _resolve_run_path(args.archive_zip)
        if str(args.archive_zip).strip()
        else (ROOT / "runs" / f"biorxiv_submission_assets_{bundle_tag}_frozen.zip").resolve()
    )
    archive_zip.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(submission_zip, archive_zip)

    audit_json_path = _resolve_run_path(str(meta.get("audit_json") or "runs/biorxiv_external_validation_audit_current.json"))
    package_zip = _resolve_run_path(
        str(
            meta.get("convenience_artifacts", {}).get("archive_zip")
            or meta.get("current_files", {}).get("archive_zip")
            or "runs/biorxiv_external_validation_package_current.zip"
        )
    )
    run_summary_json = _resolve_run_path(str(meta.get("summary_json") or ""))

    temporal = _read_json(temporal_json) if temporal_json.exists() else {}
    robustness_compare = _read_json(robustness_compare_json) if robustness_compare_json.exists() else {}

    artifacts = []
    for label, path in [
        ("current_package_meta_json", meta_path),
        ("submission_assets_zip", submission_zip),
        ("submission_assets_manifest_json", submission_manifest),
        ("frozen_submission_assets_zip", archive_zip),
        ("current_package_zip", package_zip),
        ("current_run_summary_json", run_summary_json),
        ("current_audit_json", audit_json_path),
        ("governance_seal_json", governance_seal_json),
        ("robustness_matrix_json", robustness_matrix_json),
        ("robustness_comparison_json", robustness_compare_json),
        ("temporal_submission_baseline_json", temporal_json),
    ]:
        if path.exists():
            artifacts.append(_record(label, path))

    payload = {
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "freeze_mode": "immutable_submission_baseline",
        "bundle_tag": bundle_tag,
        "promoted_at_local": meta.get("promoted_at_local"),
        "run_root": meta.get("run_root"),
        "package_root": meta.get("package_root"),
        "audit_pass": bool(meta.get("audit_pass")),
        "submission_assets_zip": str(submission_zip),
        "frozen_submission_assets_zip": str(archive_zip),
        "overall_item_ready_count": temporal.get("overall_item_ready_count"),
        "overall_dataset_ready_count": temporal.get("overall_dataset_ready_count"),
        "seed_shift_all_sets_preserved": robustness_compare.get("all_sets_preserved"),
        "seed_shift_ligand_pass_count": robustness_compare.get("ligand_pass_count"),
        "artifacts": artifacts,
    }

    out_json = _resolve_run_path(args.out_json)
    out_md = _resolve_run_path(args.out_md)
    _write_json(out_json, payload)

    lines = [
        "# bioRxiv Submission Freeze Baseline",
        "",
        f"- generated_at_local: `{payload['generated_at_local']}`",
        f"- bundle_tag: `{bundle_tag}`",
        f"- promoted_at_local: `{payload.get('promoted_at_local')}`",
        f"- audit_pass: `{payload.get('audit_pass')}`",
        f"- frozen_submission_assets_zip: `{archive_zip}`",
        f"- temporal_item_ready: `{payload.get('overall_item_ready_count')}`",
        f"- temporal_dataset_ready: `{payload.get('overall_dataset_ready_count')}`",
        f"- seed_shift_all_sets_preserved: `{payload.get('seed_shift_all_sets_preserved')}`",
        "",
        "| label | size_bytes | sha256 |",
        "| --- | ---: | --- |",
    ]
    for row in artifacts:
        lines.append(f"| {row['label']} | {row['size_bytes']} | `{row['sha256']}` |")
    _write_text(out_md, "\n".join(lines) + "\n")

    print(
        json.dumps(
            {
                "ok": True,
                "out_json": str(out_json),
                "bundle_tag": bundle_tag,
                "frozen_submission_assets_zip": str(archive_zip),
                "artifact_count": len(artifacts),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
