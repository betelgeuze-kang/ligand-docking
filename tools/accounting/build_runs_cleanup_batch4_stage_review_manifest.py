#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import OrderedDict
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNS_DIR = "runs"
DEFAULT_SOURCE_MANIFEST = "runs/runs_cleanup_batch3_review_manifest_current.json"
DEFAULT_OUT_JSON = "runs/runs_cleanup_batch4_stage_review_manifest_current.json"
DEFAULT_OUT_CSV = "runs/runs_cleanup_batch4_stage_review_manifest_current.csv"
DEFAULT_OUT_MD = "runs/runs_cleanup_batch4_stage_review_manifest_current.md"

TARGET_FAMILY_IDS = {
    "ligand_blind_gpcr",
    "ligand_blind_trpv1",
    "ligand_stress_commercial",
}
STAGE_SUBGROUPS: dict[str, dict[str, str]] = {
    "stage1_queue_inputs": {
        "stage_id": "stage1",
        "stage_label": "stage1 queue and input artifacts",
    },
    "stage2_active_learning": {
        "stage_id": "stage2",
        "stage_label": "stage2 active-learning artifacts",
    },
    "stage3_delivery_scores": {
        "stage_id": "stage3",
        "stage_label": "stage3 delivery and score artifacts",
    },
}
JSON_KEY_ORDER = [
    "generated_at_local",
    "targets",
    "target_list",
    "ligand_source",
    "ligands",
    "count",
    "queue_rows",
    "processed_rows",
    "ok_rows",
    "failed_rows",
    "unique_ligands",
    "processed_jobs",
    "score_only",
    "parallel_enabled",
    "workers_used",
    "pass",
    "avg_binding_energy_proxy",
    "avg_stability_score",
]
JSON_NESTED_KEY_ORDER = OrderedDict(
    [
        (
            "summary",
            [
                "targets_total",
                "targets_nonzero_score",
                "selected_targets_count",
                "hard_mining_selected_targets_count",
                "hard_mining_priority_targets_matched",
                "max_hard_score",
                "mean_hard_score",
            ],
        ),
        (
            "active_learning_summary",
            [
                "hard_mining_selected_targets_count",
                "hard_mining_priority_targets_matched",
                "curriculum_pass",
                "claim_pass",
            ],
        ),
        (
            "priority_sampling",
            [
                "applied",
                "priority_rows_selected",
                "priority_rows_in_queue",
                "fallback_rows_selected",
            ],
        ),
    ]
)
MARKDOWN_KEY_ORDER = [
    "generated_at_local",
    "queue_rows",
    "processed_jobs",
    "avg_binding_energy_proxy",
    "avg_stability_score",
]
MAX_SUMMARY_PARTS = 6


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _parse_sample_artifacts(raw: str) -> list[str]:
    return [item.strip() for item in str(raw).split(";") if item.strip()]


def _file_size(path: Path) -> int:
    return path.stat().st_size if path.is_file() else 0


def _format_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, float):
        text = f"{value:.4f}"
        return text.rstrip("0").rstrip(".")
    if isinstance(value, (int, str)):
        text = str(value)
        return text if len(text) <= 60 else f"{text[:57]}..."
    if isinstance(value, list):
        preview = "|".join(str(item) for item in value[:3])
        if len(value) > 3:
            preview = f"{preview}|+{len(value) - 3}more"
        return preview
    return str(value)


def _artifact_kind(name: str) -> str:
    if name.endswith("_ligands.json"):
        return "ligands_json"
    if name.endswith("_queue.csv"):
        return "queue_csv"
    if name.endswith("_scores.csv"):
        return "scores_csv"
    if name.endswith("_summary.md"):
        return "summary_md"
    if name.endswith("_summary.json"):
        return "summary_json"
    if name.endswith(".json"):
        return "json"
    if name.endswith(".csv"):
        return "csv"
    if name.endswith(".md"):
        return "md"
    return Path(name).suffix.lstrip(".") or "artifact"


def _summarize_json_file(path: Path) -> str:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return f"json_decode_error={exc.msg}"

    parts: list[str] = []
    if isinstance(data, dict):
        if "count" in data:
            parts.append(f"count={_format_scalar(data['count'])}")
        if "rows" in data and isinstance(data["rows"], list):
            parts.append(f"rows={len(data['rows'])}")
        for key in JSON_KEY_ORDER:
            if key in {"count"}:
                continue
            if key in data:
                parts.append(f"{key}={_format_scalar(data[key])}")
        for container, keys in JSON_NESTED_KEY_ORDER.items():
            nested = data.get(container)
            if not isinstance(nested, dict):
                continue
            for key in keys:
                if key in nested:
                    parts.append(f"{container}.{key}={_format_scalar(nested[key])}")
        if not parts:
            parts.append(f"keys={','.join(list(data)[:5])}")
    elif isinstance(data, list):
        parts.append(f"items={len(data)}")
    else:
        parts.append(f"value={_format_scalar(data)}")
    return ", ".join(parts[:MAX_SUMMARY_PARTS])


def _summarize_csv_file(path: Path) -> str:
    try:
        with path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.reader(fh)
            header = next(reader, [])
            row_count = 0
            target_idx = header.index("target") if "target" in header else None
            targets: set[str] = set()
            for row in reader:
                row_count += 1
                if target_idx is not None and target_idx < len(row):
                    targets.add(row[target_idx])
    except csv.Error as exc:
        return f"csv_error={exc}"

    parts = [f"rows={row_count}", f"columns={len(header)}"]
    if targets:
        parts.append(f"targets={len(targets)}")
    if header:
        parts.append(f"header={'|'.join(header[:5])}")
    return ", ".join(parts)


def _summarize_markdown_file(path: Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    title = ""
    fields: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if not title and stripped.startswith("# "):
            title = stripped[2:].strip()
            continue
        if stripped.startswith("- ") and ":" in stripped:
            key, value = stripped[2:].split(":", 1)
            fields[key.strip()] = value.strip().strip("`")

    parts: list[str] = []
    if title:
        parts.append(f"title={title}")
    for key in MARKDOWN_KEY_ORDER:
        if key in fields:
            parts.append(f"{key}={fields[key]}")
    if not parts:
        preview = [line.strip() for line in lines if line.strip()][:3]
        parts.extend(preview)
    return ", ".join(parts[:MAX_SUMMARY_PARTS])


def _summarize_artifact(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return _summarize_json_file(path)
    if suffix == ".csv":
        return _summarize_csv_file(path)
    if suffix == ".md":
        return _summarize_markdown_file(path)
    return f"size_bytes={_file_size(path)}"


def build_payload(runs_dir: str, source_manifest: str) -> dict[str, Any]:
    runs_root = _resolve(runs_dir)
    source_path = _resolve(source_manifest)
    source_payload = json.loads(source_path.read_text(encoding="utf-8"))

    family_order: list[str] = []
    family_rows_map: dict[str, dict[str, Any]] = {}
    stage_reviews: list[dict[str, Any]] = []
    sample_details: list[dict[str, Any]] = []
    sampled_size_bytes = 0
    missing_artifact_count = 0

    for row in source_payload.get("rows", []):
        family_id = str(row.get("family_id", "")).strip()
        subgroup_id = str(row.get("subgroup_id", "")).strip()
        if family_id not in TARGET_FAMILY_IDS or subgroup_id not in STAGE_SUBGROUPS:
            continue

        stage_meta = STAGE_SUBGROUPS[subgroup_id]
        if family_id not in family_rows_map:
            family_rows_map[family_id] = {
                "family_id": family_id,
                "family_label": row.get("family_label", family_id),
                "stage_review_count": 0,
                "source_match_count": 0,
                "source_size_mb": 0.0,
                "sampled_artifact_count": 0,
                "missing_artifact_count": 0,
                "review_only": True,
            }
            family_order.append(family_id)
        family_row = family_rows_map[family_id]
        family_row["stage_review_count"] += 1
        family_row["source_match_count"] += int(row.get("match_count", 0) or 0)
        family_row["source_size_mb"] = round(
            float(family_row["source_size_mb"]) + float(row.get("size_mb", 0.0) or 0.0),
            2,
        )

        artifact_names = _parse_sample_artifacts(str(row.get("sample_artifacts", "")))
        detail_summaries: list[str] = []
        formats: list[str] = []
        sampled_artifact_bytes = 0
        stage_missing = 0

        for sample_index, artifact_name in enumerate(artifact_names, start=1):
            artifact_path = runs_root / artifact_name
            exists = artifact_path.is_file()
            artifact_bytes = _file_size(artifact_path)
            summary_excerpt = _summarize_artifact(artifact_path) if exists else "missing"
            kind = _artifact_kind(artifact_name)
            detail_row = {
                "family_id": family_id,
                "family_label": row.get("family_label", family_id),
                "stage_id": stage_meta["stage_id"],
                "stage_label": stage_meta["stage_label"],
                "subgroup_id": subgroup_id,
                "artifact_index": sample_index,
                "artifact_name": artifact_name,
                "artifact_path": str(artifact_path),
                "artifact_kind": kind,
                "exists": exists,
                "size_kb": round(artifact_bytes / 1024, 2),
                "review_only": True,
                "summary_excerpt": summary_excerpt,
            }
            sample_details.append(detail_row)
            detail_summaries.append(f"{artifact_name}: {summary_excerpt}")
            formats.append(Path(artifact_name).suffix.lstrip("."))
            sampled_artifact_bytes += artifact_bytes
            sampled_size_bytes += artifact_bytes
            family_row["sampled_artifact_count"] += 1
            if not exists:
                stage_missing += 1
                family_row["missing_artifact_count"] += 1
                missing_artifact_count += 1

        stage_reviews.append(
            {
                "family_id": family_id,
                "family_label": row.get("family_label", family_id),
                "stage_id": stage_meta["stage_id"],
                "stage_label": stage_meta["stage_label"],
                "subgroup_id": subgroup_id,
                "source_match_count": int(row.get("match_count", 0) or 0),
                "source_size_mb": float(row.get("size_mb", 0.0) or 0.0),
                "recommended_disposition": row.get("recommended_disposition", ""),
                "review_only": True,
                "sampled_artifact_count": len(artifact_names),
                "missing_artifact_count": stage_missing,
                "sampled_size_kb": round(sampled_artifact_bytes / 1024, 2),
                "sampled_formats": "; ".join(sorted(set(formats))),
                "sample_artifacts": "; ".join(artifact_names),
                "sample_highlights": " | ".join(detail_summaries),
            }
        )

    families = [family_rows_map[family_id] for family_id in family_order]
    summary = {
        "status": "runs_cleanup_batch4_stage_review_manifest_ready",
        "source_manifest": str(source_path),
        "source_manifest_status": source_payload.get("summary", {}).get("status", ""),
        "runs_dir": str(runs_root),
        "family_count": len(families),
        "stage_review_count": len(stage_reviews),
        "sampled_artifact_count": len(sample_details),
        "missing_artifact_count": missing_artifact_count,
        "sampled_size_mb": round(sampled_size_bytes / (1024 * 1024), 2),
        "next_required_step": "Use these sampled stage1/stage2/stage3 summaries for a manual spot check only, and keep the broader ligand family artifacts on review hold until a separate family-level archive decision is approved.",
    }
    return {
        "summary": summary,
        "families": families,
        "stage_reviews": stage_reviews,
        "sample_details": sample_details,
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Runs Cleanup Batch4 Stage Review Manifest",
        "",
        f"- status: `{summary['status']}`",
        f"- source_manifest: `{summary['source_manifest']}`",
        f"- source_manifest_status: `{summary['source_manifest_status']}`",
        f"- runs_dir: `{summary['runs_dir']}`",
        f"- family_count: `{summary['family_count']}`",
        f"- stage_review_count: `{summary['stage_review_count']}`",
        f"- sampled_artifact_count: `{summary['sampled_artifact_count']}`",
        f"- missing_artifact_count: `{summary['missing_artifact_count']}`",
        f"- sampled_size_mb: `{summary['sampled_size_mb']}`",
        "",
        "## Family Totals",
        "",
        "| family_id | stage_review_count | source_match_count | source_size_mb | sampled_artifact_count | missing_artifact_count |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["families"]:
        lines.append(
            f"| `{row['family_id']}` | `{row['stage_review_count']}` | `{row['source_match_count']}` | `{row['source_size_mb']}` | `{row['sampled_artifact_count']}` | `{row['missing_artifact_count']}` |"
        )
    lines.extend(
        [
            "",
            "## Stage Reviews",
            "",
            "| family_id | stage_id | source_match_count | sampled_artifact_count | sampled_size_kb | missing_artifact_count | recommended_disposition |",
            "| --- | --- | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for row in payload["stage_reviews"]:
        lines.append(
            f"| `{row['family_id']}` | `{row['stage_id']}` | `{row['source_match_count']}` | `{row['sampled_artifact_count']}` | `{row['sampled_size_kb']}` | `{row['missing_artifact_count']}` | `{row['recommended_disposition']}` |"
        )
    lines.extend(["", "## Detail", ""])
    for row in payload["stage_reviews"]:
        lines.extend(
            [
                f"### {row['family_id']} / {row['stage_id']}",
                "",
                f"- stage_label: `{row['stage_label']}`",
                f"- source_match_count: `{row['source_match_count']}`",
                f"- source_size_mb: `{row['source_size_mb']}`",
                f"- sampled_artifact_count: `{row['sampled_artifact_count']}`",
                f"- sampled_formats: `{row['sampled_formats']}`",
                f"- sample_artifacts: `{row['sample_artifacts']}`",
                f"- sample_highlights: {row['sample_highlights']}",
                "",
            ]
        )
    lines.extend(
        [
            "## Sample Details",
            "",
            "| family_id | stage_id | artifact_name | artifact_kind | exists | size_kb | summary_excerpt |",
            "| --- | --- | --- | --- | --- | ---: | --- |",
        ]
    )
    for row in payload["sample_details"]:
        lines.append(
            f"| `{row['family_id']}` | `{row['stage_id']}` | `{row['artifact_name']}` | `{row['artifact_kind']}` | `{row['exists']}` | `{row['size_kb']}` | {row['summary_excerpt']} |"
        )
    lines.extend(["", "## Next Step", "", f"- {summary['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a review-only batch4 stage manifest by expanding sampled stage1/stage2/stage3 artifacts from the batch3 review manifest."
    )
    parser.add_argument("--runs-dir", default=DEFAULT_RUNS_DIR)
    parser.add_argument("--source-manifest", default=DEFAULT_SOURCE_MANIFEST)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(args.runs_dir, args.source_manifest)
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["stage_reviews"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
