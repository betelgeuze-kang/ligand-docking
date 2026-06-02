#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_CURRENT_TARGETS_JSON = "casp17/casp17_target_model_folders_current.json"
DEFAULT_FILESYSTEM_SWEEP_JSON = "casp17/casp17_strict_blind_internal_candidate_filesystem_sweep_current.json"
DEFAULT_SOURCE_GATE_JSON = "casp17/casp17_strict_blind_internal_prediction_source_gate_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_strict_blind_unknown_candidate_triage_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_strict_blind_unknown_candidate_triage_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_STRICT_BLIND_UNKNOWN_CANDIDATE_TRIAGE.md"

STRUCTURE_EXTENSIONS = {".pdb", ".cif", ".mmcif"}
TRIAGE_ORDER = [
    "internal_structure_archive_unverified",
    "public_structure_archive_not_internal",
    "wetlab_ligand_or_allatom_review_only",
    "gpcr_repair_or_profile_review_only",
    "selected_visual_or_name_index_review_only",
    "archival_smoke_or_delivery_review_only",
    "runs_other_unverified",
    "data_other_unverified",
    "tmp_or_misc_unverified",
    "other_unclassified",
]
TRIAGE_PROOF_USE = {
    "internal_structure_archive_unverified": "operator_review_only_until_source_chronology_no_leak_clearance",
    "public_structure_archive_not_internal": "blocked_public_structure_not_internal_prediction",
    "wetlab_ligand_or_allatom_review_only": "blocked_wetlab_ligand_or_repair_context_not_blind_prediction",
    "gpcr_repair_or_profile_review_only": "blocked_gpcr_repair_context_not_casp_historical_prediction",
    "selected_visual_or_name_index_review_only": "blocked_visual_bundle_or_name_index_not_source_evidence",
    "archival_smoke_or_delivery_review_only": "blocked_smoke_delivery_archive_not_blind_source",
    "runs_other_unverified": "operator_review_only_unclassified_run_artifact",
    "data_other_unverified": "operator_review_only_unclassified_data_artifact",
    "tmp_or_misc_unverified": "blocked_temporary_or_misc_artifact",
    "other_unclassified": "operator_review_only_unclassified_artifact",
}
TRIAGE_NEXT_ACTION = {
    "internal_structure_archive_unverified": (
        "inspect metadata for source_id, creation timestamp, native release chronology, no-leak evidence, "
        "and operator clearance before any strict-blind promotion"
    ),
    "public_structure_archive_not_internal": "exclude from internal proof unless separately proven to be an internal pre-native prediction",
    "wetlab_ligand_or_allatom_review_only": "keep in ligand/wetlab retrospective review; do not use as CASP strict-blind source",
    "gpcr_repair_or_profile_review_only": "keep in GPCR repair review; do not use as CASP strict-blind source",
    "selected_visual_or_name_index_review_only": "use as visual navigation only, not source evidence",
    "archival_smoke_or_delivery_review_only": "keep as archived smoke/delivery evidence only",
    "runs_other_unverified": "classify provenance before considering source-gate evidence",
    "data_other_unverified": "classify provenance before considering source-gate evidence",
    "tmp_or_misc_unverified": "ignore unless operator supplies durable source evidence",
    "other_unclassified": "classify provenance before considering source-gate evidence",
}


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    path = _resolve(path_like).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(_text(value)))
    except (TypeError, ValueError):
        return 0


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _current_target_ids(path_like: str | Path) -> set[str]:
    target_ids = set()
    for row in _rows(_read_json(path_like)):
        target_id = _text(row.get("target_id")).upper()
        if target_id:
            target_ids.add(target_id)
    return target_ids


def _path_contains_current_target(path: str, current_target_ids: set[str]) -> bool:
    upper = "/" + path.upper().replace("\\", "/")
    for target_id in current_target_ids:
        if (
            f"/{target_id}/" in upper
            or f"/{target_id}_" in upper
            or f"/{target_id}TS" in upper
            or upper.endswith(f"/{target_id}.PDB")
            or upper.endswith(f"/{target_id}.CIF")
        ):
            return True
    return False


def _base_category(path: str, current_target_ids: set[str]) -> str:
    normalized = path.replace("\\", "/").lstrip("./")
    lowered = normalized.lower()
    if "massivefold" in lowered:
        return "massivefold_external_baseline_only"
    if "official_archive" in normalized or "historical_seed_official_archive_baseline_lane" in normalized:
        return "official_archive_baseline_only"
    if (
        normalized.startswith("casp17/runs/casp17_")
        or normalized.startswith("runs/casp17_")
        or normalized.startswith("casp17/current_upload_review_packet")
        or normalized.startswith("casp17/protein_object_library_current")
        or normalized.startswith("casp17/targets_current")
        or _path_contains_current_target(normalized, current_target_ids)
    ):
        return "current_casp17_or_review_only"
    if (
        "/native/" in normalized
        or "native_candidate" in normalized
        or normalized.startswith("data/native")
        or normalized.endswith("_native.pdb")
    ):
        return "native_or_reference_not_prediction"
    if "historical_seed_top5_candidate_pools" in normalized:
        return "historical_seed_top5_post_native_review_only"
    if "strict_blind" in lowered and "dropzone" in lowered:
        return "strict_blind_dropzone_unverified"
    return "unknown_possible_internal_review"


def _triage_category(path: str) -> str:
    normalized = path.replace("\\", "/").lstrip("./")
    if normalized.startswith("data/internal_structures/") or normalized.startswith(
        "data/internal_structures_refined/"
    ):
        return "internal_structure_archive_unverified"
    if normalized.startswith("data/public_structures/"):
        return "public_structure_archive_not_internal"
    if normalized.startswith("runs/wetlab"):
        return "wetlab_ligand_or_allatom_review_only"
    if normalized.startswith("runs/gpcr"):
        return "gpcr_repair_or_profile_review_only"
    if normalized.startswith("runs/selected_allatom") or normalized.startswith("runs/_by_name"):
        return "selected_visual_or_name_index_review_only"
    if normalized.startswith("archives/"):
        return "archival_smoke_or_delivery_review_only"
    if normalized.startswith("runs/"):
        return "runs_other_unverified"
    if normalized.startswith("data/"):
        return "data_other_unverified"
    if normalized.startswith("tmp/") or normalized.startswith("/tmp/"):
        return "tmp_or_misc_unverified"
    return "other_unclassified"


def _is_atom_like(path: Path) -> bool:
    try:
        data = path.read_bytes()[:8192]
    except OSError:
        return False
    upper = data.upper()
    return b"ATOM  " in upper or b"HETATM" in upper or b"_ATOM_SITE." in upper


def _relpath(path: Path, scan_root: Path) -> str:
    try:
        return str(path.relative_to(scan_root)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _walk_structure_files(scan_root: Path, exclude_prefixes: list[str]) -> list[Path]:
    exclude = tuple(prefix.strip("/").replace("\\", "/") for prefix in exclude_prefixes if prefix)
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(scan_root):
        rel_dir = _relpath(Path(dirpath), scan_root)
        rel_dir_clean = "" if rel_dir == "." else rel_dir.strip("/")
        dirnames[:] = [
            name
            for name in dirnames
            if not any(f"{rel_dir_clean}/{name}".strip("/").startswith(prefix) for prefix in exclude)
        ]
        for filename in filenames:
            path = Path(dirpath) / filename
            if path.suffix.lower() in STRUCTURE_EXTENSIONS:
                files.append(path)
    return sorted(files)


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "triage_category",
        "file_count",
        "atom_like_count",
        "promotion_ready_count",
        "review_priority",
        "proof_use",
        "first_sample_path",
        "sample_paths",
        "blockers",
        "next_action",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Strict-Blind Unknown Candidate Triage",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- triage_status: `{summary['unknown_candidate_triage_status']}`",
        f"- unknown total: `{summary['unknown_possible_internal_review_count']}`",
        f"- promotion-ready: `{summary['promotion_ready_count']}`",
        f"- internal-like review: `{summary['internal_like_review_count']}`",
        f"- public/run/archive/data-other/tmp/other: `{summary['public_structure_count']}/{summary['run_review_count']}/{summary['archive_review_count']}/{summary['data_other_count']}/{summary['tmp_misc_count']}/{summary['other_unclassified_count']}`",
        f"- source gate: `{summary['source_gate_status'] or '-'}` `{summary['source_gate_first_blocker'] or '-'}`",
        f"- first internal-like sample: `{summary['first_internal_like_sample_path'] or '-'}`",
        "",
        "## Triage Buckets",
        "",
        "| category | files | atom-like | priority | promotion-ready | proof use | first sample |",
        "| --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['triage_category']}` | {row['file_count']} | {row['atom_like_count']} | "
            f"{row['review_priority']} | {row['promotion_ready_count']} | {row['proof_use']} | "
            f"`{row['first_sample_path'] or '-'}` |"
        )
    lines.extend(["", "## Claim Boundary", "", summary["claim_boundary"], ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    scan_root = _resolve(args.scan_root)
    current_target_ids = _current_target_ids(args.current_targets_json)
    sweep_summary = _summary(_read_json(args.filesystem_sweep_json))
    source_gate_summary = _summary(_read_json(args.source_gate_json))
    sample_limit = max(_int(args.sample_limit), 1)
    exclude_prefixes = [item for item in str(args.exclude_prefixes).split(",") if item]
    buckets: dict[str, dict[str, Any]] = {
        key: {
            "triage_category": key,
            "file_count": 0,
            "atom_like_count": 0,
            "promotion_ready_count": 0,
            "review_priority": 1 if key == "internal_structure_archive_unverified" else 2,
            "proof_use": TRIAGE_PROOF_USE[key],
            "samples": [],
            "blockers": "",
            "next_action": TRIAGE_NEXT_ACTION[key],
        }
        for key in TRIAGE_ORDER
    }
    unknown_total = 0
    for path in _walk_structure_files(scan_root, exclude_prefixes):
        rel = _relpath(path, scan_root)
        if _base_category(rel, current_target_ids) != "unknown_possible_internal_review":
            continue
        unknown_total += 1
        bucket = buckets[_triage_category(rel)]
        bucket["file_count"] += 1
        if _is_atom_like(path):
            bucket["atom_like_count"] += 1
        if len(bucket["samples"]) < sample_limit:
            bucket["samples"].append(rel)

    rows: list[dict[str, Any]] = []
    for key in TRIAGE_ORDER:
        bucket = buckets[key]
        if bucket["file_count"]:
            if key == "internal_structure_archive_unverified":
                bucket["blockers"] = "source_id_chronology_no_leak_operator_clearance_required"
            else:
                bucket["blockers"] = TRIAGE_PROOF_USE[key]
        rows.append(
            {
                "triage_category": key,
                "file_count": bucket["file_count"],
                "atom_like_count": bucket["atom_like_count"],
                "promotion_ready_count": bucket["promotion_ready_count"],
                "review_priority": bucket["review_priority"],
                "proof_use": bucket["proof_use"],
                "first_sample_path": bucket["samples"][0] if bucket["samples"] else "",
                "sample_paths": ";".join(bucket["samples"]),
                "blockers": bucket["blockers"],
                "next_action": bucket["next_action"],
            }
        )

    internal_like = buckets["internal_structure_archive_unverified"]["file_count"]
    public_count = buckets["public_structure_archive_not_internal"]["file_count"]
    run_review = sum(
        buckets[key]["file_count"]
        for key in [
            "wetlab_ligand_or_allatom_review_only",
            "gpcr_repair_or_profile_review_only",
            "selected_visual_or_name_index_review_only",
            "runs_other_unverified",
        ]
    )
    archive_review = buckets["archival_smoke_or_delivery_review_only"]["file_count"]
    data_other = buckets["data_other_unverified"]["file_count"]
    tmp_misc = buckets["tmp_or_misc_unverified"]["file_count"]
    other = buckets["other_unclassified"]["file_count"]
    if internal_like:
        status = "strict_blind_unknown_triage_internal_like_review_required"
    elif unknown_total:
        status = "strict_blind_unknown_triage_no_internal_like_candidates"
    else:
        status = "strict_blind_unknown_triage_no_unknown_files"
    claim_boundary = (
        "CASP17 strict-blind unknown candidate triage only. It narrows the filesystem sweep's unknown files "
        "into path-provenance buckets for operator review. It does not infer pre-native chronology from mtime, "
        "does not approve no-leak evidence, and does not promote any unknown file into strict-blind proof."
    )
    summary = {
        "packet_type": "casp17_strict_blind_unknown_candidate_triage",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "unknown_candidate_triage_status": status,
        "scan_root": _artifact(scan_root),
        "unknown_possible_internal_review_count": unknown_total,
        "filesystem_sweep_unknown_count": _int(sweep_summary.get("unknown_possible_internal_review_count")),
        "promotion_ready_count": 0,
        "internal_like_review_count": internal_like,
        "public_structure_count": public_count,
        "run_review_count": run_review,
        "archive_review_count": archive_review,
        "data_other_count": data_other,
        "tmp_misc_count": tmp_misc,
        "other_unclassified_count": other,
        "triage_bucket_count": len(rows),
        "nonempty_bucket_count": sum(1 for row in rows if row["file_count"]),
        "source_gate_status": _text(source_gate_summary.get("internal_prediction_source_gate_status")),
        "source_gate_first_blocker": _text(source_gate_summary.get("first_blocker")),
        "first_internal_like_sample_path": buckets["internal_structure_archive_unverified"]["samples"][0]
        if buckets["internal_structure_archive_unverified"]["samples"]
        else "",
        "next_action": (
            "start with internal_structure_archive_unverified rows; promote nothing until source_id, "
            "prediction_created_at, native_release_date, no-leak evidence, and operator_clearance are filled"
        ),
        "claim_boundary": claim_boundary,
    }
    return {"summary": summary, "rows": rows}


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Triage unknown filesystem candidates for strict-blind review.")
    parser.add_argument("--scan-root", default=".")
    parser.add_argument("--current-targets-json", default=DEFAULT_CURRENT_TARGETS_JSON)
    parser.add_argument("--filesystem-sweep-json", default=DEFAULT_FILESYSTEM_SWEEP_JSON)
    parser.add_argument("--source-gate-json", default=DEFAULT_SOURCE_GATE_JSON)
    parser.add_argument("--exclude-prefixes", default=".git,.codex,tools/bin")
    parser.add_argument("--sample-limit", default="8")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)


if __name__ == "__main__":
    main()
