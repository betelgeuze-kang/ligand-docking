#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def _copy(src: Path, dst_dir: Path) -> dict[str, Any]:
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / src.name
    shutil.copy2(src, dst)
    return {
        "src": str(src.resolve()),
        "dst": str(dst.resolve()),
        "size_bytes": dst.stat().st_size,
    }


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _bundle_name(run_root: Path) -> str:
    name = run_root.name
    prefix = "external_validation_blind_runs_"
    return name[len(prefix):] if name.startswith(prefix) else name


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _bool_badge(v: Any) -> str:
    if v is True:
        return "PASS"
    if v is False:
        return "FAIL"
    return "NA"


def _html_escape(s: Any) -> str:
    text = str(s)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a top-level bioRxiv external validation package from a completed preregistered run root.")
    ap.add_argument("--run-root", required=True, help="Run root under runs/external_validation_blind_runs/... containing summary.json.")
    ap.add_argument("--protocol-md", default="docs/biorxiv_architecture_validation_protocol.md")
    ap.add_argument("--checklist-md", default="docs/biorxiv_submission_package_checklist.md")
    ap.add_argument("--set-spec-json", default="config/external_validation_biorxiv_blind_sets_v1.json")
    ap.add_argument("--out-root", default="runs")
    ap.add_argument("--allow-partial", action=argparse.BooleanOptionalAction, default=False)
    args = ap.parse_args()

    run_root = (ROOT / args.run_root).resolve() if not Path(args.run_root).is_absolute() else Path(args.run_root).resolve()
    summary_exists = (run_root / "summary.json").exists()
    if not summary_exists and not args.allow_partial:
        raise FileNotFoundError(run_root / "summary.json")

    tag = _bundle_name(run_root)
    bundle_root = (ROOT / args.out_root / f"biorxiv_external_validation_package_{tag}").resolve()
    bundle_root.mkdir(parents=True, exist_ok=True)
    docs_dir = bundle_root / "docs"
    run_dir = bundle_root / "run"
    sets_dir = bundle_root / "sets"

    copied: list[dict[str, Any]] = []
    for rel in [args.protocol_md, args.checklist_md, args.set_spec_json]:
        copied.append(_copy((ROOT / rel).resolve(), docs_dir))

    for rel in [
        "summary.json",
        "summary.md",
        "state.json",
        "state.md",
        "oneshot_status.json",
        "oneshot_status.md",
        "validation_stage.log",
        "package_stage.log",
        "recovery_plan.json",
        "recovery_plan.md",
        "provenance.json",
        "provenance.md",
        "python_version.txt",
        "pip_freeze.txt",
        "nvidia_smi.txt",
        "environment_snapshot.json",
    ]:
        src = run_root / rel
        if src.exists():
            copied.append(_copy(src, run_dir))

    summary = _read_json(run_root / "summary.json") if summary_exists else {}
    sets = summary.get("sets", []) if isinstance(summary.get("sets"), list) else []
    if not sets and args.allow_partial:
        for set_dir in sorted(run_root.iterdir()):
            if not set_dir.is_dir():
                continue
            manifest_json = set_dir / "manifest.json"
            state_json = set_dir / "state.json"
            if manifest_json.exists():
                manifest = _read_json(manifest_json)
                sets.append(
                    {
                        "set_id": manifest.get("set_id", set_dir.name),
                        "title": manifest.get("title", set_dir.name),
                        "pass": manifest.get("pass"),
                        "manifest_json": str(manifest_json.resolve()),
                        "manifest_md": str((set_dir / "manifest.md").resolve()) if (set_dir / "manifest.md").exists() else "",
                        "zip_path": str(set_dir.with_suffix(".zip").resolve()) if set_dir.with_suffix(".zip").exists() else "",
                        "checksums_json": str((set_dir / "checksums.json").resolve()) if (set_dir / "checksums.json").exists() else "",
                        "checksums_sha256": str((set_dir / "checksums.sha256").resolve()) if (set_dir / "checksums.sha256").exists() else "",
                        "tasks": manifest.get("tasks", []),
                    }
                )
            elif state_json.exists():
                state = _read_json(state_json)
                task_rows = []
                for task_id, rec in sorted((state.get("tasks") or {}).items()):
                    task_rows.append({"task_id": task_id, **(rec.get("result") or {})})
                sets.append(
                    {
                        "set_id": set_dir.name,
                        "title": set_dir.name,
                        "pass": False,
                        "manifest_json": "",
                        "manifest_md": "",
                        "zip_path": "",
                        "checksums_json": "",
                        "checksums_sha256": "",
                        "tasks": task_rows,
                    }
                )
    set_rows: list[dict[str, Any]] = []
    failure_rows: list[dict[str, Any]] = []
    for set_row in sets:
        set_id = str(set_row.get("set_id", ""))
        if not set_id:
            continue
        dst_dir = sets_dir / set_id
        row = {"set_id": set_id, "title": str(set_row.get("title", set_id)), "pass": set_row.get("pass"), "claim_role": str(set_row.get("claim_role", "")), "files": []}
        for key in ["manifest_json", "manifest_md", "zip_path", "checksums_json", "checksums_sha256"]:
            src_str = str(set_row.get(key, "")).strip()
            if not src_str:
                continue
            src = Path(src_str).resolve()
            if src.exists():
                rec = _copy(src, dst_dir)
                copied.append(rec)
                row["files"].append({"kind": key, **rec})
        set_rows.append(row)
        if set_row.get("pass") is not True:
            failure_rows.append(
                {
                    "scope": "set",
                    "set_id": set_id,
                    "task_id": "",
                    "domain": "",
                    "kind": "",
                    "error": "set not fully passing or incomplete",
                }
            )

    claim_matrix_rows: list[dict[str, Any]] = []
    for set_row in sets:
        set_id = str(set_row.get("set_id", ""))
        for task in set_row.get("tasks", []) if isinstance(set_row.get("tasks"), list) else []:
            metrics = task.get("metrics", {}) if isinstance(task.get("metrics"), dict) else {}
            claim_matrix_rows.append(
                {
                    "set_id": set_id,
                    "claim_role": str(set_row.get("claim_role", "")),
                    "task_id": str(task.get("task_id", "")),
                    "domain": str(task.get("domain", "")),
                    "kind": str(task.get("kind", "")),
                    "pass": task.get("pass"),
                    "raw_pass": task.get("raw_pass"),
                    "ranking_unique_auc": metrics.get("ranking_unique_auc", ""),
                    "ranking_pr_auc": metrics.get("ranking_pr_auc", ""),
                    "ranking_ef1": metrics.get("ranking_ef1", ""),
                    "ranking_bedroc": metrics.get("ranking_bedroc", ""),
                    "operational_gate_pass": metrics.get("operational_gate_pass", ""),
                    "strict_gate_pass": metrics.get("strict_gate_pass", ""),
                    "ranking_pass": metrics.get("ranking_pass", ""),
                    "integrity_pass": metrics.get("integrity_pass", ""),
                    "acceptance_note": str(task.get("acceptance_note", "")),
                    "run_returncode": task.get("run_returncode", ""),
                    "run_log": str(task.get("run_log", "")),
                }
            )
            if task.get("pass") is not True:
                failure_rows.append(
                    {
                        "scope": "task",
                        "set_id": set_id,
                        "task_id": str(task.get("task_id", "")),
                        "domain": str(task.get("domain", "")),
                        "kind": str(task.get("kind", "")),
                        "error": str(task.get("acceptance_note", "") or task.get("service_failed_stage", "") or "task not passing"),
                    }
                )

    claim_csv = bundle_root / "claim_matrix.csv"
    claim_md = bundle_root / "claim_matrix.md"
    fieldnames = list(claim_matrix_rows[0].keys()) if claim_matrix_rows else [
        "set_id", "claim_role", "task_id", "domain", "kind", "pass", "raw_pass", "acceptance_note"
    ]
    with claim_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in claim_matrix_rows:
            writer.writerow(row)
    md_lines = [
        "# Claim Matrix",
        "",
        "| set_id | task_id | domain | pass | raw_pass | ranking_auc | pr_auc | ef1 | acceptance_note |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in claim_matrix_rows:
        md_lines.append(
            f"| {row['set_id']} | {row['task_id']} | {row['domain']} | {row['pass']} | {row['raw_pass']} | "
            f"{row['ranking_unique_auc']} | {row['ranking_pr_auc']} | {row['ranking_ef1']} | {row['acceptance_note']} |"
        )
    _write_text(claim_md, "\n".join(md_lines) + "\n")

    inventory_csv = bundle_root / "copied_file_inventory.csv"
    inventory_md = bundle_root / "copied_file_inventory.md"
    inv_fields = ["src", "dst", "size_bytes"]
    with inventory_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=inv_fields)
        writer.writeheader()
        for row in copied:
            writer.writerow({k: row.get(k, "") for k in inv_fields})
    _write_text(
        inventory_md,
        "# Copied File Inventory\n\n"
        + f"- file_count: `{len(copied)}`\n\n"
        + "\n".join(f"- `{row['dst']}` <- `{row['src']}`" for row in copied)
        + "\n",
    )

    failure_json = bundle_root / "failure_triage.json"
    failure_md = bundle_root / "failure_triage.md"
    _write_json(failure_json, {"failures": failure_rows})
    failure_lines = [
        "# Failure Triage",
        "",
        f"- failure_count: `{len(failure_rows)}`",
        "",
    ]
    if failure_rows:
        failure_lines.extend([
            "| scope | set_id | task_id | domain | kind | error |",
            "| --- | --- | --- | --- | --- | --- |",
        ])
        for row in failure_rows:
            failure_lines.append(
                f"| {row['scope']} | {row['set_id']} | {row['task_id']} | {row['domain']} | {row['kind']} | {row['error']} |"
            )
    _write_text(failure_md, "\n".join(failure_lines) + "\n")

    reviewer_summary = bundle_root / "reviewer_summary.md"
    total_tasks = len(claim_matrix_rows)
    pass_tasks = sum(1 for r in claim_matrix_rows if r.get("pass") is True)
    smoke_overrides = [r for r in claim_matrix_rows if str(r.get("acceptance_note", "")).strip()]
    _write_text(
        reviewer_summary,
        "# Reviewer Summary\n\n"
        + f"- bundle_tag: `{tag}`\n"
        + f"- set_count: `{len(set_rows)}`\n"
        + f"- task_count: `{total_tasks}`\n"
        + f"- effective_pass_count: `{pass_tasks}`\n"
        + f"- smoke_override_count: `{len(smoke_overrides)}`\n\n"
        + f"- failure_count: `{len(failure_rows)}`\n\n"
        + "## Interpretation\n\n"
        + "- `Core Blind Set` carries the primary cross-domain performance claim.\n"
        + "- `Expanded OOD Set` carries the out-of-distribution generalization claim.\n"
        + "- `Operational Smoke Set` is reproducibility support only.\n"
        + "- Smoke overrides, when present, preserve `raw_pass=false` and are explicitly documented in the claim matrix.\n",
    )

    reviewer_index = bundle_root / "reviewer_index.html"
    rows_html = []
    for row in claim_matrix_rows:
        badge_cls = "pass" if row.get("pass") is True else "fail"
        rows_html.append(
            "<tr>"
            f"<td>{_html_escape(row['set_id'])}</td>"
            f"<td>{_html_escape(row.get('claim_role', ''))}</td>"
            f"<td>{_html_escape(row['task_id'])}</td>"
            f"<td>{_html_escape(row['domain'])}</td>"
            f"<td><span class='badge {badge_cls}'>{_html_escape(_bool_badge(row.get('pass')))}</span></td>"
            f"<td>{_html_escape(row.get('raw_pass', ''))}</td>"
            f"<td>{_html_escape(row.get('ranking_unique_auc', ''))}</td>"
            f"<td>{_html_escape(row.get('ranking_pr_auc', ''))}</td>"
            f"<td>{_html_escape(row.get('ranking_ef1', ''))}</td>"
            f"<td>{_html_escape(row.get('acceptance_note', ''))}</td>"
            "</tr>"
        )
    reviewer_index.write_text(
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>bioRxiv External Validation Package</title>"
        "<style>"
        "body{font-family:Arial,sans-serif;max-width:1200px;margin:24px auto;padding:0 16px;color:#1f2937;}"
        "h1,h2{margin:0 0 12px 0;} .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px;margin:16px 0;}"
        ".card{border:1px solid #d1d5db;border-radius:10px;padding:14px;background:#f9fafb;}"
        ".badge{display:inline-block;padding:2px 8px;border-radius:999px;font-size:12px;font-weight:700;color:#fff;}"
        ".pass{background:#15803d;} .fail{background:#b91c1c;} .na{background:#6b7280;}"
        "table{border-collapse:collapse;width:100%;margin-top:16px;} th,td{border:1px solid #e5e7eb;padding:8px;text-align:left;font-size:13px;vertical-align:top;}"
        "th{background:#f3f4f6;} code{background:#f3f4f6;padding:2px 4px;border-radius:4px;}"
        "a{color:#1d4ed8;text-decoration:none;} a:hover{text-decoration:underline;}"
        "</style></head><body>"
        f"<h1>bioRxiv External Validation Package: {_html_escape(tag)}</h1>"
        "<div class='grid'>"
        f"<div class='card'><strong>Run Root</strong><br><code>{_html_escape(run_root)}</code></div>"
        f"<div class='card'><strong>Set Count</strong><br>{len(set_rows)}</div>"
        f"<div class='card'><strong>Task Count</strong><br>{total_tasks}</div>"
        f"<div class='card'><strong>Smoke Overrides</strong><br>{len(smoke_overrides)}</div>"
        "</div>"
        "<h2>Key Files</h2><ul>"
        f"<li><a href='run/{_html_escape((run_root / 'summary.json').name)}'>run summary.json</a></li>"
        f"<li><a href='run/{_html_escape((run_root / 'provenance.json').name)}'>provenance.json</a></li>"
        f"<li><a href='{_html_escape(claim_md.name)}'>claim_matrix.md</a></li>"
        f"<li><a href='{_html_escape(reviewer_summary.name)}'>reviewer_summary.md</a></li>"
        f"<li><a href='{_html_escape(failure_md.name)}'>failure_triage.md</a></li>"
        f"<li><a href='{_html_escape(inventory_md.name)}'>copied_file_inventory.md</a></li>"
        "</ul>"
        "<h2>Claim Matrix</h2>"
        "<table><thead><tr><th>Set</th><th>Claim Role</th><th>Task</th><th>Domain</th><th>Pass</th><th>Raw Pass</th><th>AUC</th><th>PR-AUC</th><th>EF1</th><th>Acceptance Note</th></tr></thead><tbody>"
        + "".join(rows_html)
        + "</tbody></table></body></html>",
        encoding="utf-8",
    )

    checksum_rows: list[dict[str, Any]] = []
    for path in sorted(bundle_root.rglob("*")):
        if not path.is_file():
            continue
        if path.name in {"package_manifest.json", "package_checksums.json", "package_checksums.sha256"}:
            continue
        checksum_rows.append(
            {
                "path": str(path.relative_to(bundle_root)),
                "size_bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )

    checksums_json = bundle_root / "package_checksums.json"
    checksums_sha = bundle_root / "package_checksums.sha256"
    checksums_json.write_text(json.dumps({"files": checksum_rows}, indent=2, ensure_ascii=False), encoding="utf-8")
    checksums_sha.write_text(
        "\n".join(f"{row['sha256']}  {row['path']}" for row in checksum_rows) + ("\n" if checksum_rows else ""),
        encoding="utf-8",
    )

    manifest = {
        "bundle_tag": tag,
        "run_root": str(run_root),
        "bundle_root": str(bundle_root),
        "summary_json": str((run_root / "summary.json").resolve()) if summary_exists else "",
        "partial_package": bool(args.allow_partial and not summary_exists),
        "protocol_md": str((ROOT / args.protocol_md).resolve()),
        "checklist_md": str((ROOT / args.checklist_md).resolve()),
        "set_spec_json": str((ROOT / args.set_spec_json).resolve()),
        "set_count": len(set_rows),
        "sets": set_rows,
        "copied_files": copied,
        "claim_matrix_csv": str(claim_csv.resolve()),
        "claim_matrix_md": str(claim_md.resolve()),
        "copied_file_inventory_csv": str(inventory_csv.resolve()),
        "copied_file_inventory_md": str(inventory_md.resolve()),
        "failure_triage_json": str(failure_json.resolve()),
        "failure_triage_md": str(failure_md.resolve()),
        "reviewer_summary_md": str(reviewer_summary.resolve()),
        "reviewer_index_html": str(reviewer_index.resolve()),
        "checksums_json": str(checksums_json.resolve()),
        "checksums_sha256": str(checksums_sha.resolve()),
    }
    manifest_json = bundle_root / "package_manifest.json"
    manifest_md = bundle_root / "package_manifest.md"
    manifest_json.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    manifest_md.write_text(
        "# bioRxiv External Validation Package\n\n"
        + f"- bundle_tag: `{tag}`\n"
        + f"- run_root: `{run_root}`\n"
        + f"- set_count: `{len(set_rows)}`\n"
        + f"- checksums_json: `{checksums_json.resolve()}`\n"
        + f"- checksums_sha256: `{checksums_sha.resolve()}`\n\n"
        + "## Sets\n\n"
        + "\n".join(f"- `{row['set_id']}` ({len(row['files'])} packaged files)" for row in set_rows)
        + "\n",
        encoding="utf-8",
    )

    zip_path = bundle_root.with_suffix(".zip")
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(bundle_root.rglob("*")):
            if path.is_file():
                zf.write(path, arcname=str(path.relative_to(bundle_root.parent)))

    print(
        json.dumps(
            {
                "bundle_root": str(bundle_root),
                "package_manifest_json": str(manifest_json),
                "package_manifest_md": str(manifest_md),
                "package_checksums_json": str(checksums_json),
                "package_checksums_sha256": str(checksums_sha),
                "archive_zip": str(zip_path),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
