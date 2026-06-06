#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CURRENT_TARGETS_JSON = "casp17/casp17_target_model_folders_current.json"
DEFAULT_SOURCE_GATE_JSON = "casp17/casp17_strict_blind_internal_prediction_source_gate_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_strict_blind_internal_candidate_filesystem_sweep_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_strict_blind_internal_candidate_filesystem_sweep_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_STRICT_BLIND_INTERNAL_CANDIDATE_FILESYSTEM_SWEEP.md"

STRUCTURE_EXTENSIONS = {".pdb", ".cif", ".mmcif"}
CATEGORY_ORDER = [
    "current_casp17_or_review_only",
    "massivefold_external_baseline_only",
    "official_archive_baseline_only",
    "native_or_reference_not_prediction",
    "historical_seed_top5_post_native_review_only",
    "strict_blind_dropzone_unverified",
    "unknown_possible_internal_review",
]
CATEGORY_NEXT_ACTION = {
    "current_casp17_or_review_only": "keep current CASP17 files out of historical strict-blind proof",
    "massivefold_external_baseline_only": "keep MassiveFold/AF model pools external-only and never mark as internal proof",
    "official_archive_baseline_only": "use official archive files only for baseline replay or native authority",
    "native_or_reference_not_prediction": "use native/reference files only as authority after leakage checks",
    "historical_seed_top5_post_native_review_only": "keep deterministic/post-native seed pools retrospective until pre-native evidence exists",
    "strict_blind_dropzone_unverified": "validate source manifest, timestamp, no-leak evidence, and operator clearance",
    "unknown_possible_internal_review": "operator must classify source, chronology, and no-leak evidence before any promotion",
}
CATEGORY_PROOF_USE = {
    "current_casp17_or_review_only": "blocked_current_casp17_not_historical",
    "massivefold_external_baseline_only": "blocked_external_model_pool",
    "official_archive_baseline_only": "baseline_only_not_internal_prediction",
    "native_or_reference_not_prediction": "native_authority_only_not_prediction",
    "historical_seed_top5_post_native_review_only": "retrospective_only_prediction_not_before_native_unproven",
    "strict_blind_dropzone_unverified": "operator_gate_required_before_proof",
    "unknown_possible_internal_review": "unverified_possible_internal_not_proof",
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
    payload = _read_json(path_like)
    target_ids = set()
    for row in _rows(payload):
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


def _classify(path: str, current_target_ids: set[str]) -> str:
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


def _walk_structure_files(scan_root: Path, exclude_prefixes: list[str]) -> list[Path]:
    files: list[Path] = []
    exclude = tuple(prefix.strip("/").replace("\\", "/") for prefix in exclude_prefixes if prefix)
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
        "category_id",
        "file_count",
        "atom_like_count",
        "verified_pre_native_internal_count",
        "allowed_for_strict_blind",
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
        "# CASP17 Strict-Blind Internal Candidate Filesystem Sweep",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- sweep_status: `{summary['filesystem_sweep_status']}`",
        f"- scan_root: `{summary['scan_root']}`",
        f"- scanned structure files: `{summary['scanned_structure_file_count']}`",
        f"- atom-like files: `{summary['atom_like_file_count']}`",
        f"- verified pre-native internal candidates: `{summary['verified_pre_native_internal_count']}`",
        f"- unverified possible internal review: `{summary['unknown_possible_internal_review_count']}`",
        f"- current/MassiveFold/official/native/top5/dropzone: `{summary['current_casp17_or_review_only_count']}/{summary['massivefold_external_baseline_only_count']}/{summary['official_archive_baseline_only_count']}/{summary['native_or_reference_not_prediction_count']}/{summary['historical_seed_top5_post_native_review_only_count']}/{summary['strict_blind_dropzone_unverified_count']}`",
        f"- source gate: `{summary['source_gate_status'] or '-'}` `{summary['source_gate_first_blocker'] or '-'}`",
        "",
        "## Categories",
        "",
        "| category | files | atom-like | verified | allowed | proof use | first sample |",
        "| --- | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['category_id']}` | {row['file_count']} | {row['atom_like_count']} | "
            f"{row['verified_pre_native_internal_count']} | `{row['allowed_for_strict_blind']}` | "
            f"{row['proof_use']} | `{row['first_sample_path'] or '-'}` |"
        )
    lines.extend(["", "## Claim Boundary", "", summary["claim_boundary"], ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    scan_root = _resolve(args.scan_root)
    current_target_ids = _current_target_ids(args.current_targets_json)
    source_gate_summary = _summary(_read_json(args.source_gate_json))
    exclude_prefixes = [item for item in str(args.exclude_prefixes).split(",") if item]
    sample_limit = max(_int(args.sample_limit), 1)
    category: dict[str, dict[str, Any]] = {
        key: {
            "category_id": key,
            "file_count": 0,
            "atom_like_count": 0,
            "verified_pre_native_internal_count": 0,
            "allowed_for_strict_blind": "false",
            "proof_use": CATEGORY_PROOF_USE[key],
            "samples": [],
            "blockers": "",
            "next_action": CATEGORY_NEXT_ACTION[key],
        }
        for key in CATEGORY_ORDER
    }
    for path in _walk_structure_files(scan_root, exclude_prefixes):
        rel = _relpath(path, scan_root)
        class_id = _classify(rel, current_target_ids)
        entry = category[class_id]
        entry["file_count"] += 1
        atom_like = _is_atom_like(path)
        if atom_like:
            entry["atom_like_count"] += 1
        if len(entry["samples"]) < sample_limit:
            entry["samples"].append(rel)

    rows: list[dict[str, Any]] = []
    for key in CATEGORY_ORDER:
        entry = category[key]
        if key == "unknown_possible_internal_review" and entry["file_count"]:
            entry["blockers"] = "source_class_chronology_no_leak_operator_clearance_unverified"
        elif key == "strict_blind_dropzone_unverified" and entry["file_count"]:
            entry["blockers"] = "source_gate_manifest_and_operator_evidence_required"
        elif entry["file_count"]:
            entry["blockers"] = CATEGORY_PROOF_USE[key]
        row = {
            "category_id": key,
            "file_count": entry["file_count"],
            "atom_like_count": entry["atom_like_count"],
            "verified_pre_native_internal_count": entry["verified_pre_native_internal_count"],
            "allowed_for_strict_blind": entry["allowed_for_strict_blind"],
            "proof_use": entry["proof_use"],
            "first_sample_path": entry["samples"][0] if entry["samples"] else "",
            "sample_paths": ";".join(entry["samples"]),
            "blockers": entry["blockers"],
            "next_action": entry["next_action"],
        }
        rows.append(row)

    scanned = sum(row["file_count"] for row in rows)
    verified = sum(row["verified_pre_native_internal_count"] for row in rows)
    unknown = category["unknown_possible_internal_review"]["file_count"]
    if not scanned:
        status = "blocked_no_structure_files_scanned"
    elif verified:
        status = "strict_blind_filesystem_candidate_ready_for_operator_review"
    elif unknown:
        status = "strict_blind_filesystem_sweep_operator_review_required"
    else:
        status = "strict_blind_filesystem_sweep_no_verified_internal_candidates"
    claim_boundary = (
        "CASP17 strict-blind internal candidate filesystem sweep only. It classifies local structure files by "
        "path provenance and proof boundary. It does not promote any file into strict-blind proof, does not infer "
        "pre-native chronology from filename or mtime, does not approve no-leak evidence, and does not import "
        "official, MassiveFold, current CASP17, native, or review-only files as internal predictions."
    )
    summary = {
        "packet_type": "casp17_strict_blind_internal_candidate_filesystem_sweep",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "filesystem_sweep_status": status,
        "scan_root": _artifact(scan_root),
        "current_target_count": len(current_target_ids),
        "category_count": len(rows),
        "scanned_structure_file_count": scanned,
        "atom_like_file_count": sum(row["atom_like_count"] for row in rows),
        "verified_pre_native_internal_count": verified,
        "unknown_possible_internal_review_count": unknown,
        "current_casp17_or_review_only_count": category["current_casp17_or_review_only"]["file_count"],
        "massivefold_external_baseline_only_count": category["massivefold_external_baseline_only"]["file_count"],
        "official_archive_baseline_only_count": category["official_archive_baseline_only"]["file_count"],
        "native_or_reference_not_prediction_count": category["native_or_reference_not_prediction"]["file_count"],
        "historical_seed_top5_post_native_review_only_count": category[
            "historical_seed_top5_post_native_review_only"
        ]["file_count"],
        "strict_blind_dropzone_unverified_count": category["strict_blind_dropzone_unverified"]["file_count"],
        "source_gate_status": _text(source_gate_summary.get("internal_prediction_source_gate_status")),
        "source_gate_first_blocker": _text(source_gate_summary.get("first_blocker")),
        "first_unknown_sample_path": category["unknown_possible_internal_review"]["samples"][0]
        if category["unknown_possible_internal_review"]["samples"]
        else "",
        "next_action": (
            "review unknown_possible_internal_review samples only if an operator can attach source class, "
            "pre-native chronology, no-leak evidence, and clearance; otherwise keep strict-blind proof blocked"
        ),
        "claim_boundary": claim_boundary,
    }
    return {"summary": summary, "rows": rows}


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sweep local structure files for strict-blind internal prediction candidates."
    )
    parser.add_argument("--scan-root", default=".")
    parser.add_argument("--current-targets-json", default=DEFAULT_CURRENT_TARGETS_JSON)
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
