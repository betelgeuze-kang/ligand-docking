#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REFERENCE_CSV = "config/ligand_binding_reference_blind_glut1_4pyp_v1.csv"
DEFAULT_META_CSV = "config/ligand_meta_blind_glut1_4pyp_v1.csv"
DEFAULT_SPLIT_CSV = "config/ligand_eval_splits_blind_glut1_4pyp_v1.csv"
DEFAULT_PROFILE_JSON = "config/ligand_htvs_blind_glut1_4pyp_v1.json"
DEFAULT_TARGET_CSV = "config/real_drug_targets_blind_glut1_4pyp_v1.csv"
DEFAULT_TARGET_META_CSV = "config/ligand_target_metadata_blind_glut1_4pyp_v1.csv"
DEFAULT_MANUAL_QUEUE_JSON = "runs/glut1_manual_review_queue_current.json"
DEFAULT_OUT_JSON = "runs/glut1_local_evidence_note_current.json"
DEFAULT_OUT_CSV = "runs/glut1_local_evidence_note_current.csv"
DEFAULT_OUT_MD = "runs/glut1_local_evidence_note_current.md"
TARGET_ID = "GLUT1_TRANSPORT_BLIND"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _read_csv(path_like: str) -> list[dict[str, str]]:
    with _resolve(path_like).open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _load_json(path_like: str) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def build_payload(
    reference_rows: list[dict[str, str]],
    meta_rows: list[dict[str, str]],
    split_rows: list[dict[str, str]],
    profile_payload: dict[str, Any],
    target_rows: list[dict[str, str]],
    target_meta_rows: list[dict[str, str]],
    manual_queue_payload: dict[str, Any],
) -> dict[str, Any]:
    glut1_ref = [row for row in reference_rows if str(row.get("target", "")).strip() == TARGET_ID]
    glut1_meta = [row for row in meta_rows if str(row.get("ligand_id", "")).strip().startswith("glut1_placeholder_")]
    glut1_split = [row for row in split_rows if str(row.get("target", "")).strip() == TARGET_ID]
    glut1_target = next((row for row in target_rows if str(row.get("target", "")).strip() == TARGET_ID), {})
    glut1_target_meta = next((row for row in target_meta_rows if str(row.get("target", "")).strip() == TARGET_ID), {})
    placeholder_reference_count = sum(1 for row in glut1_ref if "template_placeholder" in str(row.get("source", "")))
    placeholder_meta_count = sum(1 for row in glut1_meta if "template_placeholder" in str(row.get("scaffold", "")))
    placeholder_split_count = sum(1 for row in glut1_split if str(row.get("ligand_id", "")).strip().startswith("glut1_placeholder_"))
    binder_rows = [row for row in glut1_ref if str(row.get("is_binder", "")).strip() == "1"]
    nonbinder_rows = [row for row in glut1_ref if str(row.get("is_binder", "")).strip() == "0"]
    local_binder_evidence_curated = any("template_placeholder" not in str(row.get("source", "")) for row in binder_rows)
    local_negative_evidence_curated = any("template_placeholder" not in str(row.get("source", "")) for row in nonbinder_rows)
    manual_summary = dict(manual_queue_payload.get("summary", {}) or {})
    fit_targets = str(profile_payload.get("hard_decoy_fit_targets", "") or "")
    next_required_step = (
        "Keep all GLUT1 rows draft/manual-review only. Replace placeholder ligand reference/meta/split rows, finalize target metadata, and freeze a non-EGFR donor policy before any authoritative apply."
    )
    checks = [
        {
            "check_id": "binder_evidence",
            "status": "blocked" if not local_binder_evidence_curated else "ready",
            "signal": f"placeholder_reference_count={placeholder_reference_count}",
            "notes": "No transporter-specific GLUT1 binder evidence is locally curated yet.",
        },
        {
            "check_id": "negative_evidence",
            "status": "blocked" if not local_negative_evidence_curated else "ready",
            "signal": f"review_only_negative_count={manual_summary.get('review_only_negative_count', 0)}",
            "notes": "Negative-like GLUT1 slots stay review-only; do not inject proxy non-binder values.",
        },
        {
            "check_id": "fit_donor_policy",
            "status": "blocked" if "EGFR_KINASE" in fit_targets else "ready",
            "signal": f"hard_decoy_fit_targets={fit_targets}",
            "notes": "Current fit donor is still the temporary EGFR_KINASE placeholder.",
        },
        {
            "check_id": "ligand_packet_placeholders",
            "status": "blocked" if placeholder_reference_count or placeholder_meta_count or placeholder_split_count else "ready",
            "signal": f"ref={placeholder_reference_count}; meta={placeholder_meta_count}; split={placeholder_split_count}",
            "notes": "All six GLUT1 ligand packet rows are still placeholders.",
        },
        {
            "check_id": "target_metadata",
            "status": "blocked" if "TEMPLATE_SEQ_" in str(glut1_target_meta.get("sequence", "")) else "ready",
            "signal": f"pdb_id={glut1_target.get('pdb_id', '')}",
            "notes": "GLUT1 target metadata still carries placeholder sequence/state context in the scaffold files.",
        },
    ]
    return {
        "summary": {
            "target_id": TARGET_ID,
            "pdb_id": str(glut1_target.get("pdb_id", "")).strip(),
            "local_target_specific_binder_evidence_curated": local_binder_evidence_curated,
            "local_quantitative_negative_evidence_curated": local_negative_evidence_curated,
            "glut1_reference_row_count": len(glut1_ref),
            "glut1_meta_row_count": len(glut1_meta),
            "glut1_split_row_count": len(glut1_split),
            "placeholder_reference_count": placeholder_reference_count,
            "placeholder_meta_count": placeholder_meta_count,
            "placeholder_split_count": placeholder_split_count,
            "manual_review_only_negative_count": int(manual_summary.get("review_only_negative_count", 0) or 0),
            "manual_defer_binder_count": int(manual_summary.get("defer_binder_count", 0) or 0),
            "temporary_fit_donor_target": fit_targets,
            "dry_run": bool(profile_payload.get("dry_run", False)),
            "endpoint_status": "draft_only_local_evidence_blocked",
            "next_required_step": next_required_step,
        },
        "rows": checks,
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# GLUT1 Local Evidence Note",
        "",
        f"- target_id: `{s['target_id']}`",
        f"- pdb_id: `{s['pdb_id']}`",
        f"- local_target_specific_binder_evidence_curated: `{s['local_target_specific_binder_evidence_curated']}`",
        f"- local_quantitative_negative_evidence_curated: `{s['local_quantitative_negative_evidence_curated']}`",
        f"- glut1_reference_row_count: `{s['glut1_reference_row_count']}`",
        f"- glut1_meta_row_count: `{s['glut1_meta_row_count']}`",
        f"- glut1_split_row_count: `{s['glut1_split_row_count']}`",
        f"- placeholder_reference_count: `{s['placeholder_reference_count']}`",
        f"- placeholder_meta_count: `{s['placeholder_meta_count']}`",
        f"- placeholder_split_count: `{s['placeholder_split_count']}`",
        f"- manual_review_only_negative_count: `{s['manual_review_only_negative_count']}`",
        f"- manual_defer_binder_count: `{s['manual_defer_binder_count']}`",
        f"- temporary_fit_donor_target: `{s['temporary_fit_donor_target']}`",
        f"- endpoint_status: `{s['endpoint_status']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Checks",
        "",
        "| check_id | status | signal | notes |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(f"| {row['check_id']} | {row['status']} | `{row['signal']}` | {row['notes']} |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a local-evidence note explaining why GLUT1 remains draft/manual-review only.")
    parser.add_argument("--reference-csv", default=DEFAULT_REFERENCE_CSV)
    parser.add_argument("--meta-csv", default=DEFAULT_META_CSV)
    parser.add_argument("--split-csv", default=DEFAULT_SPLIT_CSV)
    parser.add_argument("--profile-json", default=DEFAULT_PROFILE_JSON)
    parser.add_argument("--target-csv", default=DEFAULT_TARGET_CSV)
    parser.add_argument("--target-meta-csv", default=DEFAULT_TARGET_META_CSV)
    parser.add_argument("--manual-queue-json", default=DEFAULT_MANUAL_QUEUE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _read_csv(args.reference_csv),
        _read_csv(args.meta_csv),
        _read_csv(args.split_csv),
        _load_json(args.profile_json),
        _read_csv(args.target_csv),
        _read_csv(args.target_meta_csv),
        _load_json(args.manual_queue_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
