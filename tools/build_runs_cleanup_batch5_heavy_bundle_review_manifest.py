#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNS_DIR = "runs"
DEFAULT_SOURCE_STAGE_REVIEW = "runs/runs_cleanup_batch4_stage_review_manifest_current.json"
DEFAULT_SOURCE_AUDIT = "runs/runs_cleanup_audit_current.json"
DEFAULT_OUT_JSON = "runs/runs_cleanup_batch5_heavy_bundle_review_manifest_current.json"
DEFAULT_OUT_CSV = "runs/runs_cleanup_batch5_heavy_bundle_review_manifest_current.csv"
DEFAULT_OUT_MD = "runs/runs_cleanup_batch5_heavy_bundle_review_manifest_current.md"
DEFAULT_MIN_SIZE_MB = 3.0

STAGE2_DIR_TOKENS = ("_stage2_traj_manifest_chunks", "_stage2_trajectory_frames")
STAGE3_DIR_TOKENS = ("_stage3_delivery", "_delivery")
STAGE3_FILE_TOKENS = ("_stage3_scores.csv",)

def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path_like: str) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _bundle_size_and_file_count(path: Path) -> tuple[int, int]:
    if path.is_file():
        return path.stat().st_size, 1
    size_bytes = 0
    file_count = 0
    for subpath in path.rglob("*"):
        if subpath.is_file():
            file_count += 1
            size_bytes += subpath.stat().st_size
    return size_bytes, file_count


def _sample_members(path: Path, limit: int = 3) -> list[str]:
    if path.is_file():
        return [path.name]
    members = [subpath.relative_to(path).as_posix() for subpath in sorted(path.rglob("*")) if subpath.is_file()]
    return members[:limit]


def _detect_stage_and_kind(path: Path) -> tuple[str | None, str | None]:
    name = path.name
    if path.is_dir() and any(token in name for token in STAGE2_DIR_TOKENS):
        if "_stage2_traj_manifest_chunks" in name:
            return "stage2", "stage2_manifest_chunk_dir"
        return "stage2", "stage2_frame_dir"
    if path.is_dir() and any(token in name for token in STAGE3_DIR_TOKENS):
        return "stage3", "stage3_delivery_dir"
    if path.is_file() and any(token in name for token in STAGE3_FILE_TOKENS):
        return "stage3", "stage3_scores_csv"
    return None, None


def _family_hint(name: str) -> str:
    if name.startswith("ligand_blind_gpcr") or "_gpcr_" in name:
        return "gpcr"
    if name.startswith("ligand_blind_trpv1") or "trpv1" in name or "_ion_" in name:
        return "ion_channel"
    if name.startswith("ligand_stress_commercial"):
        return "ligand_stress_commercial"
    if "_kinase_" in name:
        return "kinase"
    if name.startswith("external_validation"):
        return "external_validation_misc"
    return "misc"


def _family_id_for_stage_review(name: str) -> str | None:
    if name.startswith("ligand_blind_gpcr"):
        return "ligand_blind_gpcr"
    if name.startswith("ligand_blind_trpv1"):
        return "ligand_blind_trpv1"
    if name.startswith("ligand_stress_commercial"):
        return "ligand_stress_commercial"
    return None


def _group_label(stage_id: str, family_hint: str) -> str:
    family_labels = {
        "gpcr": "GPCR",
        "ion_channel": "ion-channel",
        "kinase": "kinase",
        "ligand_stress_commercial": "commercial-stress",
        "external_validation_misc": "external-validation",
        "misc": "misc",
    }
    return f"{stage_id} {family_labels.get(family_hint, family_hint)} heavy bundles"


def _review_priority(size_mb: float, file_count: int) -> str:
    if size_mb >= 10.0 or file_count >= 10:
        return "high"
    if size_mb >= 5.0:
        return "medium"
    return "review"


def _recommended_disposition(stage_id: str, bundle_kind: str) -> str:
    if stage_id == "stage2":
        return "manual_review_heavy_bundle"
    if bundle_kind == "stage3_scores_csv":
        return "review_for_archive_after_stage_review"
    return "manual_review_stage3_bundle"


def build_payload(
    runs_dir: str,
    source_stage_review_manifest: str,
    source_audit_artifact: str,
    min_size_mb: float = DEFAULT_MIN_SIZE_MB,
) -> dict[str, Any]:
    runs_root = _resolve(runs_dir)
    stage_review_payload = _load_json(source_stage_review_manifest)
    audit_payload = _load_json(source_audit_artifact)

    stage_review_rows = {
        (str(row.get("family_id", "")), str(row.get("stage_id", ""))): dict(row)
        for row in stage_review_payload.get("stage_reviews", []) or []
    }

    min_size_bytes = int(min_size_mb * 1024 * 1024)
    bundle_rows: list[dict[str, Any]] = []
    for path in sorted(runs_root.iterdir()):
        stage_id, bundle_kind = _detect_stage_and_kind(path)
        if stage_id is None or bundle_kind is None:
            continue
        size_bytes, file_count = _bundle_size_and_file_count(path)
        if size_bytes < min_size_bytes:
            continue
        family_hint = _family_hint(path.name)
        family_id = _family_id_for_stage_review(path.name)
        linked_stage_review = stage_review_rows.get((family_id, stage_id)) if family_id else None
        size_mb = round(size_bytes / (1024 * 1024), 2)
        bundle_rows.append(
            {
                "bundle_name": path.name,
                "bundle_path": str(path.resolve()),
                "bundle_kind": bundle_kind,
                "stage_id": stage_id,
                "family_hint": family_hint,
                "group_id": f"{stage_id}_{family_hint}_heavy_bundle",
                "group_label": _group_label(stage_id, family_hint),
                "top_level_kind": "dir" if path.is_dir() else "file",
                "file_count": file_count,
                "size_mb": size_mb,
                "sample_members": "; ".join(_sample_members(path)),
                "review_priority": _review_priority(size_mb, file_count),
                "recommended_disposition": _recommended_disposition(stage_id, bundle_kind),
                "review_only": True,
                "source_stage_review_linked": bool(linked_stage_review),
                "source_stage_review_match_count": int(linked_stage_review.get("source_match_count", 0) or 0) if linked_stage_review else 0,
                "source_stage_review_size_mb": float(linked_stage_review.get("source_size_mb", 0.0) or 0.0) if linked_stage_review else 0.0,
                "source_stage_review_sampled_artifact_count": int(linked_stage_review.get("sampled_artifact_count", 0) or 0) if linked_stage_review else 0,
            }
        )

    group_rows: list[dict[str, Any]] = []
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in bundle_rows:
        grouped[str(row["group_id"])].append(row)
    for group_id, rows in sorted(grouped.items()):
        exemplar = rows[0]
        group_rows.append(
            {
                "group_id": group_id,
                "group_label": exemplar["group_label"],
                "stage_id": exemplar["stage_id"],
                "family_hint": exemplar["family_hint"],
                "bundle_count": len(rows),
                "total_file_count": int(sum(int(r["file_count"]) for r in rows)),
                "total_size_mb": round(sum(float(r["size_mb"]) for r in rows), 2),
                "review_priority": "high" if any(r["review_priority"] == "high" for r in rows) else ("medium" if any(r["review_priority"] == "medium" for r in rows) else "review"),
                "linked_stage_review_count": int(sum(1 for r in rows if r["source_stage_review_linked"])),
                "sample_bundles": "; ".join(r["bundle_name"] for r in rows[:3]),
            }
        )

    summary = {
        "status": "runs_cleanup_batch5_heavy_bundle_review_manifest_ready",
        "runs_dir": str(runs_root),
        "source_stage_review_manifest": str(_resolve(source_stage_review_manifest)),
        "source_stage_review_status": str(stage_review_payload.get("summary", {}).get("status", "")),
        "source_audit_artifact": str(_resolve(source_audit_artifact)),
        "source_audit_status": "available" if audit_payload.get("summary") else "missing_summary",
        "heavy_size_threshold_mb": float(min_size_mb),
        "group_count": len(group_rows),
        "bundle_count": len(bundle_rows),
        "stage2_bundle_count": int(sum(1 for row in bundle_rows if row["stage_id"] == "stage2")),
        "stage3_bundle_count": int(sum(1 for row in bundle_rows if row["stage_id"] == "stage3")),
        "total_bundle_size_mb": round(sum(float(row["size_mb"]) for row in bundle_rows), 2),
        "total_bundle_file_count": int(sum(int(row["file_count"]) for row in bundle_rows)),
        "linked_stage_review_bundle_count": int(sum(1 for row in bundle_rows if row["source_stage_review_linked"])),
        "next_required_step": "Use this manifest to review remaining stage2 chunk directories and heavy stage3 delivery bundles after batch4 sampling, then archive only the explicitly accepted legacy bundles by group.",
    }
    return {"summary": summary, "groups": group_rows, "bundles": bundle_rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Runs Cleanup Batch5 Heavy Bundle Review Manifest",
        "",
        f"- status: `{summary['status']}`",
        f"- source_stage_review_manifest: `{summary['source_stage_review_manifest']}`",
        f"- source_stage_review_status: `{summary['source_stage_review_status']}`",
        f"- source_audit_artifact: `{summary['source_audit_artifact']}`",
        f"- source_audit_status: `{summary['source_audit_status']}`",
        f"- runs_dir: `{summary['runs_dir']}`",
        f"- heavy_size_threshold_mb: `{summary['heavy_size_threshold_mb']}`",
        f"- group_count: `{summary['group_count']}`",
        f"- bundle_count: `{summary['bundle_count']}`",
        f"- stage2_bundle_count: `{summary['stage2_bundle_count']}`",
        f"- stage3_bundle_count: `{summary['stage3_bundle_count']}`",
        f"- total_bundle_size_mb: `{summary['total_bundle_size_mb']}`",
        f"- total_bundle_file_count: `{summary['total_bundle_file_count']}`",
        f"- linked_stage_review_bundle_count: `{summary['linked_stage_review_bundle_count']}`",
        "",
        "## Group Totals",
        "",
        "| group_id | stage_id | bundle_count | total_file_count | total_size_mb | review_priority | linked_stage_review_count |",
        "| --- | --- | ---: | ---: | ---: | --- | ---: |",
    ]
    for row in payload["groups"]:
        lines.append(
            f"| `{row['group_id']}` | `{row['stage_id']}` | `{row['bundle_count']}` | `{row['total_file_count']}` | `{row['total_size_mb']}` | `{row['review_priority']}` | `{row['linked_stage_review_count']}` |"
        )
    lines.extend([
        "",
        "## Bundle Detail",
        "",
        "| bundle_name | stage_id | bundle_kind | family_hint | file_count | size_mb | review_priority | linked_stage_review | recommended_disposition |",
        "| --- | --- | --- | --- | ---: | ---: | --- | --- | --- |",
    ])
    for row in payload["bundles"]:
        lines.append(
            f"| `{row['bundle_name']}` | `{row['stage_id']}` | `{row['bundle_kind']}` | `{row['family_hint']}` | `{row['file_count']}` | `{row['size_mb']}` | `{row['review_priority']}` | `{row['source_stage_review_linked']}` | `{row['recommended_disposition']}` |"
        )
    lines.extend(["", "## Notes", ""])
    current_group = None
    for row in payload["bundles"]:
        if row["group_id"] != current_group:
            current_group = row["group_id"]
            lines.extend([f"### {row['group_id']}", ""])
        lines.extend(
            [
                f"- bundle_name: `{row['bundle_name']}`",
                f"- bundle_kind: `{row['bundle_kind']}`",
                f"- file_count: `{row['file_count']}`",
                f"- size_mb: `{row['size_mb']}`",
                f"- sample_members: `{row['sample_members']}`",
                f"- linked_stage_review: `{row['source_stage_review_linked']}`",
                f"- recommended_disposition: `{row['recommended_disposition']}`",
                "",
            ]
        )
    lines.extend(["## Next Step", "", f"- {summary['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a batch5 review manifest for remaining heavy stage2/stage3 bundles after batch4 sampling.")
    parser.add_argument("--runs-dir", default=DEFAULT_RUNS_DIR)
    parser.add_argument("--source-stage-review-manifest", default=DEFAULT_SOURCE_STAGE_REVIEW)
    parser.add_argument("--source-audit-artifact", default=DEFAULT_SOURCE_AUDIT)
    parser.add_argument("--min-size-mb", type=float, default=DEFAULT_MIN_SIZE_MB)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        runs_dir=args.runs_dir,
        source_stage_review_manifest=args.source_stage_review_manifest,
        source_audit_artifact=args.source_audit_artifact,
        min_size_mb=args.min_size_mb,
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["bundles"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
