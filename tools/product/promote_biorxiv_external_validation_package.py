#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "runs"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _copy_if_exists(src: Path, dst: Path) -> str:
    if not src.exists():
        return ""
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return str(dst.resolve())


def main() -> int:
    ap = argparse.ArgumentParser(description="Promote a completed bioRxiv external validation package to the current reviewer-ready baseline.")
    ap.add_argument("--package-root", required=True)
    ap.add_argument("--audit-json", default="")
    ap.add_argument("--out-root", default="runs")
    args = ap.parse_args()

    package_root = Path(args.package_root).resolve() if Path(args.package_root).is_absolute() else (ROOT / args.package_root).resolve()
    manifest_json = package_root / "package_manifest.json"
    if not manifest_json.exists():
        raise FileNotFoundError(manifest_json)
    manifest = _read_json(manifest_json)

    if bool(manifest.get("partial_package", False)):
        raise SystemExit("refusing to promote partial package as current reviewer-ready baseline")

    run_summary = Path(str(manifest.get("summary_json", "")).strip()) if str(manifest.get("summary_json", "")).strip() else None
    if not (run_summary and run_summary.exists()):
        raise SystemExit("refusing to promote package without completed run summary")

    audit_json = Path(args.audit_json).resolve() if args.audit_json else package_root / "audit.json"
    if not audit_json.exists():
        raise FileNotFoundError(audit_json)
    audit = _read_json(audit_json)
    if not bool(audit.get("pass", False)):
        raise SystemExit("refusing to promote package with failing audit")

    tag = str(manifest.get("bundle_tag", package_root.name)).strip()
    out_root = (ROOT / args.out_root).resolve() if not Path(args.out_root).is_absolute() else Path(args.out_root).resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    current_meta_json = out_root / "biorxiv_external_validation_package_current.json"
    current_meta_md = out_root / "biorxiv_external_validation_package_current.md"

    convenience = {
        "package_manifest_json": _copy_if_exists(package_root / "package_manifest.json", out_root / "biorxiv_external_validation_package_manifest_current.json"),
        "package_manifest_md": _copy_if_exists(package_root / "package_manifest.md", out_root / "biorxiv_external_validation_package_manifest_current.md"),
        "reviewer_summary_md": _copy_if_exists(package_root / "reviewer_summary.md", out_root / "biorxiv_external_validation_reviewer_summary_current.md"),
        "reviewer_index_html": _copy_if_exists(package_root / "reviewer_index.html", out_root / "biorxiv_external_validation_reviewer_index_current.html"),
        "claim_matrix_csv": _copy_if_exists(package_root / "claim_matrix.csv", out_root / "biorxiv_external_validation_claim_matrix_current.csv"),
        "claim_matrix_md": _copy_if_exists(package_root / "claim_matrix.md", out_root / "biorxiv_external_validation_claim_matrix_current.md"),
        "failure_triage_json": _copy_if_exists(package_root / "failure_triage.json", out_root / "biorxiv_external_validation_failure_triage_current.json"),
        "failure_triage_md": _copy_if_exists(package_root / "failure_triage.md", out_root / "biorxiv_external_validation_failure_triage_current.md"),
        "audit_json": _copy_if_exists(package_root / "audit.json", out_root / "biorxiv_external_validation_audit_current.json"),
        "audit_md": _copy_if_exists(package_root / "audit.md", out_root / "biorxiv_external_validation_audit_current.md"),
        "archive_zip": _copy_if_exists(package_root.with_suffix(".zip"), out_root / "biorxiv_external_validation_package_current.zip"),
    }

    payload = {
        "promoted_at_local": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "bundle_tag": tag,
        "package_root": str(package_root.resolve()),
        "run_root": str(manifest.get("run_root", "")),
        "summary_json": str(run_summary.resolve()),
        "audit_json": str(audit_json.resolve()),
        "audit_pass": bool(audit.get("pass", False)),
        "partial_package": False,
        "convenience_artifacts": convenience,
    }
    _write_json(current_meta_json, payload)
    _write_text(
        current_meta_md,
        "# bioRxiv External Validation Package Current\n\n"
        + f"- bundle_tag: `{tag}`\n"
        + f"- package_root: `{package_root.resolve()}`\n"
        + f"- run_root: `{payload['run_root']}`\n"
        + f"- audit_pass: `{payload['audit_pass']}`\n"
        + f"- reviewer_index_html: `{convenience['reviewer_index_html']}`\n"
        + f"- archive_zip: `{convenience['archive_zip']}`\n",
    )

    print(json.dumps({
        "current_meta_json": str(current_meta_json.resolve()),
        "current_meta_md": str(current_meta_md.resolve()),
        **convenience,
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
