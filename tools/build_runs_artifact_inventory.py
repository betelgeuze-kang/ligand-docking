#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from tools.lib.artifacts import artifact, resolve, short_error, write_csv, write_json

DEFAULT_RUNS_DIR = "runs"
DEFAULT_OUT_JSON = "runs/runs_artifact_inventory_current.json"
DEFAULT_OUT_CSV = "runs/runs_artifact_inventory_current.csv"
DEFAULT_OUT_MD = "runs/runs_artifact_inventory_current.md"
DEFAULT_TOP_N = 50
DEFAULT_MAX_REFERENCE_READ_MB = 20.0
DEFAULT_LARGE_THRESHOLD_MB = 10.0
DEFAULT_REFERENCE_ROOTS = [
    "commercialization_status_report.md",
    "runs/accuracy_parity_scorecard_current.json",
    "runs/gpcr_a1_accuracy_repair_queue_current.json",
    "runs/gpcr_drd2_atom_typed_backmapping_support_current.json",
    "runs/gpcr_drd2_full_forcefield_minimization_readiness_current.json",
    "runs/gpcr_drd2_local_minimization_survival_current.json",
    "runs/gpcr_drd2_openmm_forcefield_parameterization_probe_current.json",
    "runs/gpcr_drd2_protein_amber14_parameterization_repair_current.json",
    "runs/structure_refinement_metric_materialization_current.json",
    "runs/structure_refinement_metric_queue_current.json",
    "runs/structure_refinement_scorecard_current.json",
]

RUNS_REF_RE = re.compile(r"(?:/[^\s,\"'`<>\]\)]+/)?runs/[^\s,\"'`<>\]\)]+")
DATE_STAMP_RE = re.compile(r"(?:20\d{2}[-_]\d{2}[-_]\d{2}|20\d{6})")
HEAVY_INTERMEDIATE_TOKENS = (
    "_stage1_",
    "_stage2_",
    "_stage3_",
    "_stage3_scores",
    "_stage4_",
    "_stage45_",
    "shadow_replay_scores",
    "traj_frames",
    "traj_manifest",
    "trajectory",
    "candidate_scores",
    "candidate_batch",
    "docking_scores",
    "external_validation_stage3",
    "stage_heavy",
)
HEAVY_EXTENSIONS = {
    ".dcd",
    ".db",
    ".h5",
    ".hdf5",
    ".npz",
    ".parquet",
    ".pkl",
    ".pt",
    ".sqlite",
    ".xtc",
}
LOG_EXTENSIONS = {".err", ".log", ".out", ".pid", ".tmp"}


def _size_mb(size_bytes: int) -> float:
    return round(size_bytes / (1024 * 1024), 3)


def _size_gb(size_bytes: int) -> float:
    return round(size_bytes / (1024 * 1024 * 1024), 3)


def _display_path(path: Path, runs_dir: Path) -> str:
    try:
        return str(Path(runs_dir.name) / path.relative_to(runs_dir))
    except ValueError:
        return artifact(path)


def _runs_display_from_ref(raw_ref: str, runs_dir: Path) -> str:
    ref = raw_ref.strip().strip("`'\"").rstrip(".,;:")
    marker = "/runs/"
    if marker in ref:
        ref = "runs/" + ref.rsplit(marker, 1)[1]
    if ref.startswith("runs/"):
        return str(Path(runs_dir.name) / Path(ref).relative_to("runs"))
    return ref


def _path_from_runs_display(display_path: str, runs_dir: Path) -> Path:
    path = Path(display_path)
    if path.parts and path.parts[0] == runs_dir.name:
        return runs_dir / Path(*path.parts[1:])
    return resolve(display_path)


def _extract_runs_refs(text: str, runs_dir: Path) -> set[str]:
    refs: set[str] = set()
    for match in RUNS_REF_RE.finditer(text):
        refs.add(_runs_display_from_ref(match.group(0), runs_dir))
    return refs


def _read_reference_text(path: Path, max_reference_read_bytes: int) -> tuple[str, str]:
    if not path.exists():
        return "", "missing"
    if not path.is_file():
        return "", "not_file"
    try:
        size = path.stat().st_size
    except OSError as exc:
        return "", short_error(exc)
    if size > max_reference_read_bytes:
        return "", f"skipped_large_reference_{_size_mb(size)}mb"
    try:
        return path.read_text(encoding="utf-8", errors="replace"), "read"
    except OSError as exc:
        return "", short_error(exc)


def _reference_roots(paths: list[str] | None) -> list[str]:
    return paths if paths is not None else list(DEFAULT_REFERENCE_ROOTS)


def collect_references(
    *,
    reference_roots: list[str] | None,
    runs_dir: Path,
    max_reference_read_mb: float = DEFAULT_MAX_REFERENCE_READ_MB,
) -> tuple[set[str], dict[str, list[str]], list[dict[str, Any]], set[str]]:
    max_reference_read_bytes = int(max_reference_read_mb * 1024 * 1024)
    direct_roots: set[str] = set()
    refs_by_seed: dict[str, list[str]] = defaultdict(list)
    seed_rows: list[dict[str, Any]] = []

    for raw_root in _reference_roots(reference_roots):
        root_path = resolve(raw_root)
        seed_display = _display_path(root_path, runs_dir) if runs_dir in root_path.parents or root_path == runs_dir else artifact(root_path)
        if root_path.exists() and root_path.is_file():
            if root_path == runs_dir or runs_dir in root_path.parents:
                direct_roots.add(_display_path(root_path, runs_dir))
        text, status = _read_reference_text(root_path, max_reference_read_bytes)
        refs = sorted(_extract_runs_refs(text, runs_dir)) if text else []
        for ref in refs:
            refs_by_seed[ref].append(seed_display)
        seed_rows.append(
            {
                "reference_root": seed_display,
                "status": status,
                "referenced_runs_path_count": len(refs),
            }
        )

    return set(refs_by_seed), dict(refs_by_seed), seed_rows, direct_roots


def _is_current_path(display_path: str) -> bool:
    return any("_current" in part or part == "current" for part in Path(display_path).parts)


def _top_level_group(display_path: str) -> str:
    parts = Path(display_path).parts
    if len(parts) <= 2:
        return "(root)"
    return parts[1]


def _is_existing_archive(display_path: str) -> bool:
    parts = Path(display_path).parts
    return len(parts) > 1 and parts[1] == "archive"


def _is_heavy_intermediate(display_path: str, suffix: str, size_bytes: int, large_threshold_bytes: int) -> bool:
    lower = display_path.lower()
    return (
        suffix in HEAVY_EXTENSIONS
        or any(token in lower for token in HEAVY_INTERMEDIATE_TOKENS)
        or ("scores" in lower and suffix in {".csv", ".jsonl"})
        or size_bytes >= large_threshold_bytes
    )


def _classify(
    *,
    display_path: str,
    suffix: str,
    size_bytes: int,
    direct_roots: set[str],
    referenced: set[str],
    large_threshold_bytes: int,
) -> tuple[str, str, str]:
    lower = display_path.lower()
    if display_path in direct_roots:
        return "keep_reference_root", "keep", "direct reference root for commercial/current evidence"
    if display_path in referenced:
        return "keep_referenced_evidence", "keep", "referenced by commercial/current evidence root"
    if _is_existing_archive(display_path):
        return "keep_existing_archive", "keep", "already under runs/archive; leave archive policy separate"
    if _is_current_path(display_path):
        return "keep_current_artifact", "keep", "current artifact naming convention"
    if size_bytes == 0:
        return "delete_candidate_empty_or_tiny", "delete_review", "zero-byte unreferenced non-current artifact"
    if suffix in LOG_EXTENSIONS or lower.endswith(".lock"):
        return "review_lock_or_log", "manual_review", "unreferenced lock/log/temp artifact"
    if _is_heavy_intermediate(display_path, suffix, size_bytes, large_threshold_bytes):
        return "archive_candidate_large_intermediate", "archive_review", "unreferenced heavy stage/score/trajectory artifact"
    if DATE_STAMP_RE.search(display_path):
        return "archive_candidate_stale_run", "archive_review", "unreferenced dated artifact without current marker"
    return "manual_review_unclassified", "manual_review", "unreferenced non-current artifact with no safe bulk rule"


def _row_for_file(
    path: Path,
    *,
    runs_dir: Path,
    direct_roots: set[str],
    referenced: set[str],
    refs_by_seed: dict[str, list[str]],
    large_threshold_bytes: int,
) -> dict[str, Any]:
    stat = path.lstat()
    display_path = _display_path(path, runs_dir)
    suffix = path.suffix.lower()
    classification, cleanup_action, reason = _classify(
        display_path=display_path,
        suffix=suffix,
        size_bytes=stat.st_size,
        direct_roots=direct_roots,
        referenced=referenced,
        large_threshold_bytes=large_threshold_bytes,
    )
    seeds = refs_by_seed.get(display_path, [])
    return {
        "path": display_path,
        "file_kind": "symlink" if path.is_symlink() else "file",
        "symlink_target": str(path.readlink()) if path.is_symlink() else "",
        "size_bytes": stat.st_size,
        "size_mb": _size_mb(stat.st_size),
        "mtime_iso": datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds"),
        "extension": suffix or "(none)",
        "top_level_group": _top_level_group(display_path),
        "is_current_name": _is_current_path(display_path),
        "is_reference_root": display_path in direct_roots,
        "referenced_by_seed": "; ".join(seeds),
        "classification": classification,
        "cleanup_action": cleanup_action,
        "reason": reason,
    }


def _counter_rows(counter: Counter[str], size_by_key: dict[str, int], *, key_name: str) -> list[dict[str, Any]]:
    return [
        {
            key_name: key,
            "file_count": count,
            "size_gb": _size_gb(size_by_key.get(key, 0)),
        }
        for key, count in counter.most_common()
    ]


def _compact_rows(rows: list[dict[str, Any]], *, top_n: int) -> dict[str, list[dict[str, Any]]]:
    largest = sorted(rows, key=lambda row: int(row["size_bytes"]), reverse=True)[:top_n]
    largest_archive = [
        row
        for row in sorted(rows, key=lambda row: int(row["size_bytes"]), reverse=True)
        if row["cleanup_action"] == "archive_review"
    ][:top_n]
    delete_candidates = [row for row in rows if row["cleanup_action"] == "delete_review"][:top_n]
    manual_review = [row for row in rows if row["cleanup_action"] == "manual_review"][:top_n]
    return {
        "largest_files": largest,
        "largest_archive_candidates": largest_archive,
        "delete_review_samples": delete_candidates,
        "manual_review_samples": manual_review,
    }


def build_inventory(
    *,
    runs_dir: str | Path = DEFAULT_RUNS_DIR,
    reference_roots: list[str] | None = None,
    generated_at_local: str | None = None,
    top_n: int = DEFAULT_TOP_N,
    max_reference_read_mb: float = DEFAULT_MAX_REFERENCE_READ_MB,
    large_threshold_mb: float = DEFAULT_LARGE_THRESHOLD_MB,
) -> dict[str, Any]:
    root = resolve(runs_dir)
    referenced, refs_by_seed, seed_rows, direct_roots = collect_references(
        reference_roots=reference_roots,
        runs_dir=root,
        max_reference_read_mb=max_reference_read_mb,
    )
    large_threshold_bytes = int(large_threshold_mb * 1024 * 1024)

    rows: list[dict[str, Any]] = []
    scan_errors: list[dict[str, str]] = []
    if root.exists():
        for path in sorted(root.rglob("*")):
            if not path.is_file() and not path.is_symlink():
                continue
            try:
                rows.append(
                    _row_for_file(
                        path,
                        runs_dir=root,
                        direct_roots=direct_roots,
                        referenced=referenced,
                        refs_by_seed=refs_by_seed,
                        large_threshold_bytes=large_threshold_bytes,
                    )
                )
            except OSError as exc:
                scan_errors.append({"path": _display_path(path, root), "error": short_error(exc)})

    existing_paths = {str(row["path"]) for row in rows}
    referenced_existing = sorted(ref for ref in referenced if ref in existing_paths or _path_from_runs_display(ref, root).exists())
    referenced_missing = sorted(
        ref for ref in referenced if ref not in existing_paths and not _path_from_runs_display(ref, root).exists()
    )

    class_counter: Counter[str] = Counter()
    action_counter: Counter[str] = Counter()
    ext_counter: Counter[str] = Counter()
    group_counter: Counter[str] = Counter()
    class_sizes: dict[str, int] = defaultdict(int)
    action_sizes: dict[str, int] = defaultdict(int)
    ext_sizes: dict[str, int] = defaultdict(int)
    group_sizes: dict[str, int] = defaultdict(int)
    total_bytes = 0

    for row in rows:
        size = int(row["size_bytes"])
        total_bytes += size
        classification = str(row["classification"])
        action = str(row["cleanup_action"])
        extension = str(row["extension"])
        group = str(row["top_level_group"])
        class_counter[classification] += 1
        action_counter[action] += 1
        ext_counter[extension] += 1
        group_counter[group] += 1
        class_sizes[classification] += size
        action_sizes[action] += size
        ext_sizes[extension] += size
        group_sizes[group] += size

    compact = _compact_rows(rows, top_n=top_n)
    summary = {
        "status": "runs_artifact_inventory_ready",
        "generated_at_local": generated_at_local or datetime.now().astimezone().isoformat(timespec="seconds"),
        "runs_dir": str(root),
        "total_file_count": len(rows),
        "total_size_gb": _size_gb(total_bytes),
        "reference_root_count": len(seed_rows),
        "referenced_path_count": len(referenced),
        "referenced_existing_count": len(referenced_existing),
        "referenced_missing_count": len(referenced_missing),
        "direct_reference_root_count": len(direct_roots),
        "keep_file_count": action_counter.get("keep", 0),
        "keep_size_gb": _size_gb(action_sizes.get("keep", 0)),
        "archive_candidate_file_count": action_counter.get("archive_review", 0),
        "archive_candidate_size_gb": _size_gb(action_sizes.get("archive_review", 0)),
        "delete_candidate_file_count": action_counter.get("delete_review", 0),
        "delete_candidate_size_gb": _size_gb(action_sizes.get("delete_review", 0)),
        "manual_review_file_count": action_counter.get("manual_review", 0),
        "manual_review_size_gb": _size_gb(action_sizes.get("manual_review", 0)),
        "scan_error_count": len(scan_errors),
        "large_threshold_mb": large_threshold_mb,
        "max_reference_read_mb": max_reference_read_mb,
        "next_required_step": "Review archive_review/delete_review rows, then build an archive-first apply script with explicit signoff before moving or deleting files.",
    }
    return {
        "summary": summary,
        "reference_roots": seed_rows,
        "missing_references": referenced_missing[:top_n],
        "scan_errors": scan_errors[:top_n],
        "counts_by_classification": _counter_rows(class_counter, class_sizes, key_name="classification"),
        "counts_by_action": _counter_rows(action_counter, action_sizes, key_name="cleanup_action"),
        "counts_by_extension": _counter_rows(ext_counter, ext_sizes, key_name="extension"),
        "counts_by_top_level_group": _counter_rows(group_counter, group_sizes, key_name="top_level_group")[:top_n],
        **compact,
        "rows": rows,
    }


def compact_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key != "rows"}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Runs Artifact Inventory",
        "",
        f"- status: `{summary['status']}`",
        f"- generated_at_local: `{summary['generated_at_local']}`",
        f"- runs_dir: `{summary['runs_dir']}`",
        f"- total_file_count: `{summary['total_file_count']}`",
        f"- total_size_gb: `{summary['total_size_gb']}`",
        f"- keep_file_count: `{summary['keep_file_count']}`",
        f"- keep_size_gb: `{summary['keep_size_gb']}`",
        f"- archive_candidate_file_count: `{summary['archive_candidate_file_count']}`",
        f"- archive_candidate_size_gb: `{summary['archive_candidate_size_gb']}`",
        f"- delete_candidate_file_count: `{summary['delete_candidate_file_count']}`",
        f"- delete_candidate_size_gb: `{summary['delete_candidate_size_gb']}`",
        f"- manual_review_file_count: `{summary['manual_review_file_count']}`",
        f"- manual_review_size_gb: `{summary['manual_review_size_gb']}`",
        f"- referenced_existing_count: `{summary['referenced_existing_count']}`",
        f"- referenced_missing_count: `{summary['referenced_missing_count']}`",
        "",
        "## Cleanup Actions",
        "",
        "| cleanup_action | file_count | size_gb |",
        "| --- | ---: | ---: |",
    ]
    for row in payload["counts_by_action"]:
        lines.append(f"| `{row['cleanup_action']}` | `{row['file_count']}` | `{row['size_gb']}` |")

    lines.extend(["", "## Classifications", "", "| classification | file_count | size_gb |", "| --- | ---: | ---: |"])
    for row in payload["counts_by_classification"]:
        lines.append(f"| `{row['classification']}` | `{row['file_count']}` | `{row['size_gb']}` |")

    lines.extend(["", "## Largest Archive Candidates", "", "| path | size_mb | classification | reason |", "| --- | ---: | --- | --- |"])
    for row in payload["largest_archive_candidates"][:20]:
        lines.append(f"| `{row['path']}` | `{row['size_mb']}` | `{row['classification']}` | {row['reason']} |")

    lines.extend(["", "## Largest Files", "", "| path | size_mb | cleanup_action | classification |", "| --- | ---: | --- | --- |"])
    for row in payload["largest_files"][:20]:
        lines.append(f"| `{row['path']}` | `{row['size_mb']}` | `{row['cleanup_action']}` | `{row['classification']}` |")

    if payload["missing_references"]:
        lines.extend(["", "## Missing References", "", "| path |", "| --- |"])
        for ref in payload["missing_references"][:20]:
            lines.append(f"| `{ref}` |")

    lines.extend(["", "## Next Step", "", f"- {summary['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a conservative read-only inventory for files under runs/.")
    parser.add_argument("--runs-dir", default=DEFAULT_RUNS_DIR)
    parser.add_argument("--reference-root", action="append", dest="reference_roots")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--top-n", type=int, default=DEFAULT_TOP_N)
    parser.add_argument("--max-reference-read-mb", type=float, default=DEFAULT_MAX_REFERENCE_READ_MB)
    parser.add_argument("--large-threshold-mb", type=float, default=DEFAULT_LARGE_THRESHOLD_MB)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_inventory(
        runs_dir=args.runs_dir,
        reference_roots=args.reference_roots,
        top_n=args.top_n,
        max_reference_read_mb=args.max_reference_read_mb,
        large_threshold_mb=args.large_threshold_mb,
    )
    write_json(args.out_json, compact_payload(payload))
    write_csv(args.out_csv, payload["rows"])
    _write_markdown(resolve(args.out_md), payload)


if __name__ == "__main__":
    main()
