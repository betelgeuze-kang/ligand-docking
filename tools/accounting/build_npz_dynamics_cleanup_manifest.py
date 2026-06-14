#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from tools.accounting.build_storage_retention_manifest import (
    DEFAULT_SOURCE_OF_TRUTH_JSON,
    _collect_path_values,
    _display,
    _human_size,
    _read_json,
    _resolve,
    _source_of_truth_references,
)
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/npz_dynamics_cleanup_manifest_current.json"
DEFAULT_OUT_CSV = "runs/npz_dynamics_cleanup_manifest_current.csv"
DEFAULT_OUT_MD = "runs/npz_dynamics_cleanup_manifest_current.md"
DEFAULT_EXCLUDED_CURRENT_JSON_NAMES = {
    Path(DEFAULT_OUT_JSON).name,
}

DYNAMICS_SUFFIXES = {".npz", ".dcd", ".xtc", ".trr", ".nc", ".h5", ".hdf5"}
DYNAMICS_TOKENS = (
    "stage2_traj_frames",
    "stage2_trajectory_frames",
    "trajectory_frames",
    "traj_frames",
    "trajectory",
    "dynamics",
    "frames",
)

CLAIM_BOUNDARY = (
    "NPZ/dynamics cleanup manifest only; it inventories local generated dynamics payloads and marks "
    "unreferenced stale trajectory files for possible deletion after approval. It does not delete, move, "
    "archive, externalize, rewrite git history, upload, commit, push, run docking, or mutate external state."
)


def _normalize_ref(value: str, *, root: Path) -> str:
    text = str(value or "").strip().strip("\"'")
    if not text:
        return ""
    path = Path(text)
    if path.is_absolute():
        try:
            return str(path.resolve().relative_to(root))
        except (OSError, ValueError):
            return text
    return text.lstrip("./")


def _is_current_json(path: Path) -> bool:
    return path.is_file() and path.name.endswith("_current.json")


def _collect_current_json_references(
    root: Path,
    runs_dir: str = "runs",
    excluded_names: set[str] | None = None,
) -> tuple[set[str], int]:
    runs_root = _resolve(runs_dir, root=root)
    refs: set[str] = set()
    source_count = 0
    excluded = excluded_names or set()
    if not runs_root.exists():
        return refs, source_count
    for path in sorted(runs_root.rglob("*_current.json")):
        if not _is_current_json(path):
            continue
        if path.name in excluded:
            continue
        payload, present = _read_json(path, root=root)
        if not present:
            continue
        source_count += 1
        for ref in _collect_path_values(payload):
            normalized = _normalize_ref(ref, root=root)
            if normalized:
                refs.add(normalized)
        for ref in _collect_path_like_strings(payload):
            normalized = _normalize_ref(ref, root=root)
            if normalized:
                refs.add(normalized)
    return refs, source_count


def _candidate_tokens(text: str) -> list[str]:
    cleaned = text.replace('"', " ").replace("'", " ").replace(",", " ").replace(";", " ")
    return [token.strip().strip("()[]{}") for token in cleaned.split() if token.strip()]


def _looks_path_like(text: str) -> bool:
    if not text or text.startswith(("http://", "https://", "mailto:")):
        return False
    if "/" not in text:
        return False
    suffix = Path(text).suffix.lower()
    if suffix in DYNAMICS_SUFFIXES:
        return True
    lower = text.lower()
    return any(token in lower for token in DYNAMICS_TOKENS)


def _collect_path_like_strings(value: Any) -> list[str]:
    refs: list[str] = []
    if isinstance(value, dict):
        for item in value.values():
            refs.extend(_collect_path_like_strings(item))
        return refs
    if isinstance(value, list):
        for item in value:
            refs.extend(_collect_path_like_strings(item))
        return refs
    if isinstance(value, str):
        for token in [value.strip(), *_candidate_tokens(value)]:
            if _looks_path_like(token):
                refs.append(token)
    return refs


def _exact_refs_for_path(refs: set[str], rel_path: str) -> list[str]:
    normalized = rel_path.strip().lstrip("./")
    return sorted(ref for ref in refs if ref.rstrip("/") == normalized)


def _parent_refs_for_path(refs: set[str], rel_path: str) -> list[str]:
    normalized = rel_path.strip().lstrip("./")
    matches: list[str] = []
    for ref in refs:
        ref_norm = ref.rstrip("/")
        if ref_norm == normalized:
            continue
        if ref_norm and ref_norm != "runs" and "/" in ref_norm and normalized.startswith(f"{ref_norm}/"):
            matches.append(ref)
    return sorted(matches)


def _is_dynamics_payload(rel_path: str) -> bool:
    lower = rel_path.lower()
    return Path(rel_path).suffix.lower() in DYNAMICS_SUFFIXES and any(token in lower for token in DYNAMICS_TOKENS)


def _is_current_payload(rel_path: str) -> bool:
    parts = Path(rel_path).parts
    return any(part.endswith("_current") or part == "current" or "_current_" in part for part in parts)


def _cleanup_class(rel_path: str) -> str:
    suffix = Path(rel_path).suffix.lower()
    lower = rel_path.lower()
    if suffix == ".npz" and "stage2_traj" in lower:
        return "stage2_npz_trajectory_bundle"
    if suffix == ".npz" and "trajectory" in lower:
        return "npz_trajectory_bundle"
    if suffix == ".npz":
        return "npz_generated_payload"
    if suffix in DYNAMICS_SUFFIXES:
        return "dynamics_payload"
    return "non_dynamics_payload"


def _disposition(
    *,
    rel_path: str,
    current_refs: list[str],
    source_refs: list[str],
    parent_refs: list[str],
) -> tuple[str, bool, str]:
    if current_refs or source_refs:
        return (
            "keep_referenced_current_evidence",
            False,
            "Path is exactly referenced by current JSON/source-of-truth evidence.",
        )
    if not _is_dynamics_payload(rel_path):
        return (
            "review_non_dynamics_npz_payload",
            False,
            "NPZ-like file is not clearly a trajectory/dynamics payload.",
        )
    if _is_current_payload(rel_path):
        return (
            "review_current_regenerable_dynamics_payload",
            False,
            "Current-named generated payload may be regenerable, but should be reviewed before deletion.",
        )
    if parent_refs:
        return (
            "delete_after_json_manifest_approval",
            True,
            "Parent trajectory directory is referenced, but this file is not exact-referenced; keep JSON path/size record before deletion.",
        )
    return (
        "delete_after_json_manifest_approval",
        True,
        "Unreferenced generated trajectory/dynamics payload; keep JSON manifest record and delete after approval.",
    )


def _iter_candidates(root: Path) -> list[Path]:
    candidates: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in DYNAMICS_SUFFIXES:
            continue
        candidates.append(path)
    return sorted(candidates)


def build_npz_dynamics_cleanup_manifest(
    *,
    root: str | Path = ROOT,
    source_of_truth_json: str | Path = DEFAULT_SOURCE_OF_TRUTH_JSON,
    runs_dir: str = "runs",
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    source_of_truth, source_present = _read_json(source_of_truth_json, root=root_path)
    source_refs = set(_normalize_ref(ref, root=root_path) for ref in _source_of_truth_references(source_of_truth))
    source_refs.discard("")
    current_refs, current_json_source_count = _collect_current_json_references(
        root_path,
        runs_dir=runs_dir,
        excluded_names=DEFAULT_EXCLUDED_CURRENT_JSON_NAMES,
    )

    rows: list[dict[str, Any]] = []
    for path in _iter_candidates(root_path):
        rel_path = _display(path, root=root_path)
        size = path.stat().st_size
        current_path_refs = _exact_refs_for_path(current_refs, rel_path)
        source_path_refs = _exact_refs_for_path(source_refs, rel_path)
        parent_path_refs = _parent_refs_for_path(current_refs | source_refs, rel_path)
        disposition, delete_recommended, reason = _disposition(
            rel_path=rel_path,
            current_refs=current_path_refs,
            source_refs=source_path_refs,
            parent_refs=parent_path_refs,
        )
        rows.append(
            {
                "path": rel_path,
                "size_bytes": size,
                "size_human": _human_size(size),
                "mtime_epoch_utc": f"{path.stat().st_mtime:.6f}",
                "suffix": path.suffix.lower(),
                "cleanup_class": _cleanup_class(rel_path),
                "disposition": disposition,
                "delete_recommended": delete_recommended,
                "current_json_reference_count": len(current_path_refs),
                "source_of_truth_reference_count": len(source_path_refs),
                "parent_reference_count": len(parent_path_refs),
                "parent_references": ";".join(parent_path_refs[:10]),
                "preserve_json_record": True,
                "sha256_status": "deferred_size_and_path_record_only",
                "delete_allowed_by_this_tool": False,
                "delete_executed": False,
                "archive_executed": False,
                "externalize_executed": False,
                "external_state_mutated": False,
                "reason": reason,
            }
        )

    delete_rows = [row for row in rows if row["delete_recommended"]]
    referenced_rows = [row for row in rows if row["current_json_reference_count"] or row["source_of_truth_reference_count"]]
    review_rows = [row for row in rows if not row["delete_recommended"] and row not in referenced_rows]
    class_counts = Counter(str(row["cleanup_class"]) for row in rows)
    disposition_counts = Counter(str(row["disposition"]) for row in rows)
    dir_sizes: dict[str, int] = defaultdict(int)
    dir_counts: dict[str, int] = defaultdict(int)
    for row in delete_rows:
        parent = str(Path(str(row["path"])).parent)
        dir_sizes[parent] += int(row["size_bytes"])
        dir_counts[parent] += 1
    top_delete_dirs = [
        {
            "directory": directory,
            "delete_recommended_count": dir_counts[directory],
            "delete_recommended_size_bytes": size,
            "delete_recommended_size_human": _human_size(size),
        }
        for directory, size in sorted(dir_sizes.items(), key=lambda item: (-item[1], item[0]))[:20]
    ]
    total_size = sum(int(row["size_bytes"]) for row in rows)
    delete_size = sum(int(row["size_bytes"]) for row in delete_rows)
    referenced_size = sum(int(row["size_bytes"]) for row in referenced_rows)
    review_size = sum(int(row["size_bytes"]) for row in review_rows)
    summary = {
        "packet_type": "npz_dynamics_cleanup_manifest",
        "status": "npz_dynamics_cleanup_manifest_ready",
        "source_of_truth_json": _display(_resolve(source_of_truth_json, root=root_path), root=root_path),
        "source_of_truth_present": source_present,
        "current_json_source_count": current_json_source_count,
        "candidate_count": len(rows),
        "candidate_size_bytes": total_size,
        "candidate_size_human": _human_size(total_size),
        "delete_recommended_count": len(delete_rows),
        "delete_recommended_size_bytes": delete_size,
        "delete_recommended_size_human": _human_size(delete_size),
        "referenced_keep_count": len(referenced_rows),
        "referenced_keep_size_bytes": referenced_size,
        "referenced_keep_size_human": _human_size(referenced_size),
        "review_required_count": len(review_rows),
        "review_required_size_bytes": review_size,
        "review_required_size_human": _human_size(review_size),
        "class_counts": dict(sorted(class_counts.items())),
        "disposition_counts": dict(sorted(disposition_counts.items())),
        "cleanup_allowed_count": 0,
        "delete_executed": False,
        "archive_executed": False,
        "externalize_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": "Review delete_recommended rows, then run a separate approval-gated deletion step if acceptable.",
    }
    return {"summary": summary, "top_delete_directories": top_delete_dirs, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    s = payload["summary"]
    lines = [
        "# NPZ Dynamics Cleanup Manifest",
        "",
        f"- status: `{s['status']}`",
        f"- candidate_count: `{s['candidate_count']}`",
        f"- candidate_size_human: `{s['candidate_size_human']}`",
        f"- delete_recommended_count: `{s['delete_recommended_count']}`",
        f"- delete_recommended_size_human: `{s['delete_recommended_size_human']}`",
        f"- referenced_keep_count: `{s['referenced_keep_count']}`",
        f"- referenced_keep_size_human: `{s['referenced_keep_size_human']}`",
        f"- review_required_count: `{s['review_required_count']}`",
        f"- review_required_size_human: `{s['review_required_size_human']}`",
        f"- cleanup_allowed_count: `{s['cleanup_allowed_count']}`",
        f"- delete_executed: `{s['delete_executed']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Top Delete-Recommended Directories",
        "",
        "| directory | files | size |",
        "| --- | ---: | ---: |",
    ]
    for row in payload["top_delete_directories"]:
        lines.append(
            f"| `{row['directory']}` | `{row['delete_recommended_count']}` | `{row['delete_recommended_size_human']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a read-only JSON manifest for NPZ/dynamics cleanup candidates.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--source-of-truth-json", default=DEFAULT_SOURCE_OF_TRUTH_JSON)
    parser.add_argument("--runs-dir", default="runs")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    root = Path(args.root)
    payload = build_npz_dynamics_cleanup_manifest(
        root=root,
        source_of_truth_json=args.source_of_truth_json,
        runs_dir=args.runs_dir,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["rows"])
    _write_markdown(args.out_md, payload, root=root)


if __name__ == "__main__":
    main()
