#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from tools.accounting.build_npz_dynamics_cleanup_manifest import (
    _collect_path_like_strings,
    _exact_refs_for_path,
    _normalize_ref,
    _parent_refs_for_path,
)
from tools.accounting.build_storage_retention_manifest import (
    DEFAULT_SOURCE_OF_TRUTH_JSON,
    _collect_path_values,
    _display,
    _human_size,
    _read_json,
    _resolve,
    _size_bytes,
    _source_of_truth_references,
)
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/ligand_heavy_run_cleanup_manifest_current.json"
DEFAULT_OUT_CSV = "runs/ligand_heavy_run_cleanup_manifest_current.csv"
DEFAULT_OUT_MD = "runs/ligand_heavy_run_cleanup_manifest_current.md"
DEFAULT_CURRENT_JSON_MAX_BYTES = 0
DEFAULT_EXCLUDED_CURRENT_JSON_NAMES = {
    Path(DEFAULT_OUT_JSON).name,
}

LIGAND_SCOPE_TOKENS = (
    "ligand",
    "htvs",
    "blind",
    "external_validation",
    "gpcr",
    "dude_z",
    "lit_pcba",
    "adrb2",
)

TOP_RANKING_KEEP_TOKENS = (
    "stage5_ranking_topk",
    "stage5_ranking_unique",
    "stage5_ranking_summary",
    "ranking_topk",
    "ranking_unique",
    "ranking_summary",
    "ranking_eval_topk",
    "ranking_eval_unique",
    "ranking_eval_rows",
    "ranking_eval_current",
    "shadow_replay_eval_topk",
    "shadow_replay_eval_unique",
    "shadow_replay_eval_current",
    "_eval_topk",
    "_eval_unique",
    "_eval_current",
)

COMPACT_KEEP_TOKENS = (
    "stage3_refine_scores_shortlist",
    "summary",
    "claim_split",
    "sla_summary",
    "status",
    "wrapper_status",
    "latest_status",
    "scorecard",
)

RAW_FILE_DELETE_TOKENS = (
    "stage1_ligands.json",
    "stage1_queue.csv",
    "stage2_traj_manifest.csv",
    "stage2_traj_merged_manifest.csv",
    "stage2_traj_routed_queue.csv",
    "stage2_traj_skip_manifest.csv",
    "stage2_priority_targets.csv",
    "stage2_ood_pair_proxy.csv",
    "stage2_active_learning_hard_scores.csv",
    "stage2_active_learning_target_weights.csv",
    "stage2_ligand_target_stats.csv",
    "stage3_scores.csv",
    "stage3_refine_scores.csv",
    "stage3b_physics_refinement_scores.csv",
    "stage4_calibration_scores.csv",
    "stage4_calibration_model.json",
    "stage5_ranking_rows.csv",
    "hard_decoy_labels.csv",
    "hard_decoy_labels_balanced.csv",
    "hard_decoy_split.csv",
    "labels_pos",
    "split_pos",
    "shadow_replay_scores",
    "replay_scores",
    "admet_surface.csv",
    "admet_surface.json",
    "_aggregate.csv",
    "_runs.csv",
    "_state.json",
)

TRANSIENT_FILE_SUFFIXES = (".log", ".lock")

RAW_DIR_DELETE_TOKENS = (
    "stage2_traj_frames",
    "stage2_trajectory_frames",
    "stage2_traj_manifest_chunks",
    "stage3_delivery",
)

RUN_PREFIX_MARKERS = (
    "_stage1_",
    "_stage2_",
    "_stage3b_",
    "_stage3_",
    "_stage4_",
    "_stage5_",
    "_shadow_replay_scores",
    "_replay_scores",
    "_hard_decoy_",
    "_labels_pos",
    "_split_pos",
    "_admet_surface",
    "_claim_split",
    "_sla_summary",
    "_aggregate.",
    "_runs.",
    "_state.",
    ".log",
    ".lock",
)

CLAIM_BOUNDARY = (
    "Ligand-heavy run cleanup manifest only; it inventories local generated ligand/HTVS run payloads and "
    "marks old raw/stage artifacts for deletion only when compact top-ranking or summary evidence is present. "
    "It does not delete, move, archive, externalize, rewrite git history, upload, commit, push, run docking, "
    "or mutate external state."
)


def _in_ligand_scope(name: str) -> bool:
    lower = name.lower()
    return any(token in lower for token in LIGAND_SCOPE_TOKENS)


def _is_top_ranking_or_compact_keep(name: str) -> bool:
    lower = name.lower()
    return any(token in lower for token in TOP_RANKING_KEEP_TOKENS + COMPACT_KEEP_TOKENS)


def _is_raw_file_delete_shape(name: str) -> bool:
    lower = name.lower()
    return lower.endswith(TRANSIENT_FILE_SUFFIXES) or any(token in lower for token in RAW_FILE_DELETE_TOKENS)


def _is_raw_dir_delete_shape(name: str) -> bool:
    lower = name.lower()
    return any(token in lower for token in RAW_DIR_DELETE_TOKENS)


def _is_current_named(rel_path: str) -> bool:
    parts = Path(rel_path).parts
    return any(part == "current" or part.endswith("_current") or "_current_" in part for part in parts)


def _run_prefix(name: str) -> str:
    lower = name.lower()
    marker_positions = [lower.find(marker) for marker in RUN_PREFIX_MARKERS if lower.find(marker) >= 0]
    if not marker_positions:
        return Path(name).stem
    return name[: min(marker_positions)]


def _evidence_globs(prefix: str) -> tuple[str, ...]:
    return (
        f"{prefix}*stage5_ranking_topk.csv",
        f"{prefix}*stage5_ranking_unique.csv",
        f"{prefix}*stage5_ranking_rows.csv",
        f"{prefix}*stage5_ranking_summary.json",
        f"{prefix}*stage5_ranking_summary.md",
        f"{prefix}*ranking_topk*.csv",
        f"{prefix}*ranking_unique*.csv",
        f"{prefix}*ranking_rows*.csv",
        f"{prefix}*ranking_eval_unique*.csv",
        f"{prefix}*ranking_eval_rows*.csv",
        f"{prefix}*ranking_eval_topk*.csv",
        f"{prefix}*ranking_eval_current*.json",
        f"{prefix}*ranking_eval_current*.md",
        f"{prefix}*ranking_summary*.json",
        f"{prefix}*ranking_summary*.md",
        f"{prefix}*eval_topk*.csv",
        f"{prefix}*eval_unique*.csv",
        f"{prefix}*eval_current*.json",
        f"{prefix}*eval_current*.md",
        f"{prefix}*stage3_refine_scores_shortlist.csv",
        f"{prefix}*stage3_refine_scores_shortlist.json",
        f"{prefix}*summary.json",
        f"{prefix}*summary.md",
        f"{prefix}*claim_split.json",
        f"{prefix}*claim_split.md",
        f"{prefix}*sla_summary.json",
        f"{prefix}*sla_summary.md",
        f"{prefix}*status.json",
        f"{prefix}*status.md",
    )


def _candidate_size_bytes(path: Path) -> int:
    if path.is_file() or path.is_symlink():
        try:
            return path.lstat().st_size
        except OSError:
            return 0
    return _size_bytes(path)


def _collect_limited_current_json_references(
    root: Path,
    *,
    runs_dir: str,
    excluded_names: set[str],
    current_json_max_bytes: int,
) -> tuple[set[str], int, int, int]:
    runs_root = _resolve(runs_dir, root=root)
    refs: set[str] = set()
    source_count = 0
    skipped_count = 0
    skipped_size = 0
    if not runs_root.exists():
        return refs, source_count, skipped_count, skipped_size
    for path in sorted(runs_root.rglob("*_current.json")):
        if not path.is_file() or path.name in excluded_names:
            continue
        size = path.stat().st_size
        if current_json_max_bytes >= 0 and size > current_json_max_bytes:
            skipped_count += 1
            skipped_size += size
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
    return refs, source_count, skipped_count, skipped_size


def _build_preserved_evidence_index(runs_root: Path, *, root: Path) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    if not runs_root.exists():
        return rows
    for candidate in sorted(runs_root.iterdir()):
        if not candidate.is_file():
            continue
        if not _in_ligand_scope(candidate.name):
            continue
        if not _is_top_ranking_or_compact_keep(candidate.name):
            continue
        rows.append((candidate.name, _display(candidate, root=root)))
    return rows


def _preserved_evidence_for(path: Path, *, evidence_index: list[tuple[str, str]]) -> list[str]:
    prefix = _run_prefix(path.name)
    if not prefix:
        return []
    seen: set[str] = set()
    rows: list[str] = []
    for name, rel in evidence_index:
        if rel == str(path):
            continue
        if name == path.name:
            continue
        if not name.startswith(prefix):
            continue
        if not any(Path(rel).match(f"runs/{pattern}") or name == pattern for pattern in _evidence_globs(prefix)):
            continue
        if rel in seen:
            continue
        seen.add(rel)
        rows.append(rel)
        if len(rows) >= 20:
            break
    return rows[:20]


def _path_type(path: Path) -> str:
    if path.is_dir():
        return "directory"
    if path.is_file():
        return "file"
    if path.is_symlink():
        return "symlink"
    return "other"


def _cleanup_class(path: Path) -> str:
    name = path.name.lower()
    if any(token in name for token in TOP_RANKING_KEEP_TOKENS):
        return "top_ranking_evidence"
    if any(token in name for token in COMPACT_KEEP_TOKENS):
        return "compact_ligand_evidence"
    if path.is_dir() and "stage2_traj_frames" in name:
        return "raw_stage2_trajectory_sidecar"
    if path.is_dir() and "stage2_trajectory_frames" in name:
        return "raw_stage2_trajectory_sidecar"
    if path.is_dir() and "stage2_traj_manifest_chunks" in name:
        return "raw_stage2_manifest_chunks_sidecar"
    if path.is_dir() and "stage3_delivery" in name:
        return "raw_stage3_delivery_sidecar"
    if "stage1_ligands" in name:
        return "raw_stage1_ligand_inventory"
    if "hard_decoy" in name and ("labels" in name or "split" in name):
        return "raw_hard_decoy_labels"
    if "labels_pos" in name or "split_pos" in name:
        return "raw_label_or_split_payload"
    if "shadow_replay_scores" in name or "replay_scores" in name:
        return "raw_replay_score_payload"
    if "admet_surface" in name and not name.endswith(".md"):
        return "raw_admet_surface"
    if "stage5_ranking_rows" in name:
        return "raw_full_ranking_rows"
    if "stage3" in name and name.endswith("_scores.csv"):
        return "raw_stage3_scores"
    if "stage4" in name and "calibration" in name:
        return "raw_stage4_calibration"
    if name.endswith(TRANSIENT_FILE_SUFFIXES):
        return "transient_ligand_run_log_or_lock"
    return "ligand_run_payload_review"


def _age_days(path: Path, *, now: float) -> float:
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return 0.0
    return max(0.0, (now - mtime) / 86_400)


def _is_candidate_path(path: Path) -> bool:
    if not _in_ligand_scope(path.name):
        return False
    if path.is_dir():
        return _is_raw_dir_delete_shape(path.name)
    if not path.is_file():
        return False
    return _is_raw_file_delete_shape(path.name) or _is_top_ranking_or_compact_keep(path.name)


def _disposition(
    *,
    path: Path,
    rel_path: str,
    age: float,
    older_than_days: int,
    current_refs: list[str],
    source_refs: list[str],
    parent_refs: list[str],
    preserved_evidence: list[str],
) -> tuple[str, bool, str]:
    name = path.name.lower()
    if current_refs or source_refs:
        return (
            "keep_referenced_current_evidence",
            False,
            "Path is exactly referenced by current JSON/source-of-truth evidence.",
        )
    if _is_top_ranking_or_compact_keep(path.name):
        return (
            "keep_top_ranking_or_compact_evidence",
            False,
            "Top-ranking, shortlist, summary, claim, SLA, or status evidence is preserved.",
        )
    if _is_current_named(rel_path):
        return (
            "review_current_named_ligand_payload",
            False,
            "Current-named payload is not deleted by the local ligand cleanup manifest.",
        )
    if age < older_than_days:
        return (
            "review_recent_ligand_payload",
            False,
            "Payload is newer than the cleanup age threshold.",
        )
    raw_shape = _is_raw_dir_delete_shape(path.name) if path.is_dir() else _is_raw_file_delete_shape(path.name)
    if raw_shape and preserved_evidence:
        return (
            "delete_after_top_rank_manifest_approval",
            True,
            "Old raw ligand run payload has compact top-ranking or summary evidence preserved.",
        )
    if raw_shape and name.endswith(TRANSIENT_FILE_SUFFIXES):
        return (
            "delete_after_top_rank_manifest_approval",
            True,
            "Old ligand run log/lock is transient and a compact JSON path/size record is preserved.",
        )
    if raw_shape and parent_refs:
        return (
            "review_parent_referenced_ligand_payload",
            False,
            "Parent path is referenced; review before deleting this raw ligand payload.",
        )
    if raw_shape:
        return (
            "review_missing_top_rank_evidence",
            False,
            "Raw ligand payload has no matching top-ranking or compact summary evidence in the manifest scope.",
        )
    return (
        "review_unclassified_ligand_payload",
        False,
        "Ligand-scoped payload is not recognized as top-ranking evidence or a safe raw cleanup shape.",
    )


def _iter_candidates(root: Path, runs_dir: str) -> list[Path]:
    runs_root = _resolve(runs_dir, root=root)
    if not runs_root.exists():
        return []
    return sorted(path for path in runs_root.iterdir() if _is_candidate_path(path))


def build_ligand_heavy_run_cleanup_manifest(
    *,
    root: str | Path = ROOT,
    source_of_truth_json: str | Path = DEFAULT_SOURCE_OF_TRUTH_JSON,
    runs_dir: str = "runs",
    older_than_days: int = 7,
    current_json_max_bytes: int = DEFAULT_CURRENT_JSON_MAX_BYTES,
    now: float | None = None,
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    runs_root = _resolve(runs_dir, root=root_path)
    source_of_truth, source_present = _read_json(source_of_truth_json, root=root_path)
    source_refs = set(_normalize_ref(ref, root=root_path) for ref in _source_of_truth_references(source_of_truth))
    source_refs.discard("")
    (
        current_refs,
        current_json_source_count,
        current_json_skipped_large_count,
        current_json_skipped_large_size,
    ) = _collect_limited_current_json_references(
        root_path,
        runs_dir=runs_dir,
        excluded_names=DEFAULT_EXCLUDED_CURRENT_JSON_NAMES,
        current_json_max_bytes=current_json_max_bytes,
    )
    observed_now = time.time() if now is None else now
    evidence_index = _build_preserved_evidence_index(runs_root, root=root_path)

    rows: list[dict[str, Any]] = []
    for path in _iter_candidates(root_path, runs_dir):
        rel_path = _display(path, root=root_path)
        size = _candidate_size_bytes(path)
        age = _age_days(path, now=observed_now)
        current_path_refs = _exact_refs_for_path(current_refs, rel_path)
        source_path_refs = _exact_refs_for_path(source_refs, rel_path)
        parent_path_refs = _parent_refs_for_path(current_refs | source_refs, rel_path)
        preserved_evidence = _preserved_evidence_for(path, evidence_index=evidence_index)
        disposition, delete_recommended, reason = _disposition(
            path=path,
            rel_path=rel_path,
            age=age,
            older_than_days=older_than_days,
            current_refs=current_path_refs,
            source_refs=source_path_refs,
            parent_refs=parent_path_refs,
            preserved_evidence=preserved_evidence,
        )
        rows.append(
            {
                "path": rel_path,
                "path_type": _path_type(path),
                "size_bytes": size,
                "size_human": _human_size(size),
                "mtime_epoch_utc": f"{path.stat().st_mtime:.6f}",
                "age_days": round(age, 2),
                "run_prefix": _run_prefix(path.name),
                "cleanup_class": _cleanup_class(path),
                "disposition": disposition,
                "delete_recommended": delete_recommended,
                "preserved_evidence_count": len(preserved_evidence),
                "preserved_evidence": ";".join(preserved_evidence[:10]),
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
    top_rank_keep_rows = [row for row in rows if row["disposition"] == "keep_top_ranking_or_compact_evidence"]
    referenced_rows = [row for row in rows if row["current_json_reference_count"] or row["source_of_truth_reference_count"]]
    review_rows = [row for row in rows if not row["delete_recommended"] and row not in top_rank_keep_rows and row not in referenced_rows]
    class_counts = Counter(str(row["cleanup_class"]) for row in rows)
    disposition_counts = Counter(str(row["disposition"]) for row in rows)
    path_type_counts = Counter(str(row["path_type"]) for row in rows)
    delete_sizes: dict[str, int] = defaultdict(int)
    delete_counts: dict[str, int] = defaultdict(int)
    for row in delete_rows:
        klass = str(row["cleanup_class"])
        delete_sizes[klass] += int(row["size_bytes"])
        delete_counts[klass] += 1
    top_delete_classes = [
        {
            "cleanup_class": cleanup_class,
            "delete_recommended_count": delete_counts[cleanup_class],
            "delete_recommended_size_bytes": size,
            "delete_recommended_size_human": _human_size(size),
        }
        for cleanup_class, size in sorted(delete_sizes.items(), key=lambda item: (-item[1], item[0]))[:20]
    ]
    top_delete_paths = [
        {
            "path": str(row["path"]),
            "cleanup_class": str(row["cleanup_class"]),
            "path_type": str(row["path_type"]),
            "size_bytes": int(row["size_bytes"]),
            "size_human": str(row["size_human"]),
        }
        for row in sorted(delete_rows, key=lambda item: (-int(item["size_bytes"]), str(item["path"])))[:20]
    ]
    total_size = sum(int(row["size_bytes"]) for row in rows)
    delete_size = sum(int(row["size_bytes"]) for row in delete_rows)
    top_rank_size = sum(int(row["size_bytes"]) for row in top_rank_keep_rows)
    referenced_size = sum(int(row["size_bytes"]) for row in referenced_rows)
    review_size = sum(int(row["size_bytes"]) for row in review_rows)
    summary = {
        "packet_type": "ligand_heavy_run_cleanup_manifest",
        "status": "ligand_heavy_run_cleanup_manifest_ready",
        "source_of_truth_json": _display(_resolve(source_of_truth_json, root=root_path), root=root_path),
        "source_of_truth_present": source_present,
        "runs_dir": _display(runs_root, root=root_path),
        "older_than_days": older_than_days,
        "current_json_max_bytes": current_json_max_bytes,
        "current_json_source_count": current_json_source_count,
        "current_json_skipped_large_count": current_json_skipped_large_count,
        "current_json_skipped_large_size_bytes": current_json_skipped_large_size,
        "current_json_skipped_large_size_human": _human_size(current_json_skipped_large_size),
        "candidate_count": len(rows),
        "candidate_size_bytes": total_size,
        "candidate_size_human": _human_size(total_size),
        "delete_recommended_count": len(delete_rows),
        "delete_recommended_size_bytes": delete_size,
        "delete_recommended_size_human": _human_size(delete_size),
        "top_rank_keep_count": len(top_rank_keep_rows),
        "top_rank_keep_size_bytes": top_rank_size,
        "top_rank_keep_size_human": _human_size(top_rank_size),
        "referenced_keep_count": len(referenced_rows),
        "referenced_keep_size_bytes": referenced_size,
        "referenced_keep_size_human": _human_size(referenced_size),
        "review_required_count": len(review_rows),
        "review_required_size_bytes": review_size,
        "review_required_size_human": _human_size(review_size),
        "path_type_counts": dict(sorted(path_type_counts.items())),
        "class_counts": dict(sorted(class_counts.items())),
        "disposition_counts": dict(sorted(disposition_counts.items())),
        "cleanup_allowed_count": 0,
        "delete_executed": False,
        "archive_executed": False,
        "externalize_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": "Review delete_recommended rows, then run the approval-gated deletion step if acceptable.",
    }
    return {
        "summary": summary,
        "top_delete_classes": top_delete_classes,
        "top_delete_paths": top_delete_paths,
        "rows": rows,
    }


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    s = payload["summary"]
    lines = [
        "# Ligand Heavy Run Cleanup Manifest",
        "",
        f"- status: `{s['status']}`",
        f"- older_than_days: `{s['older_than_days']}`",
        f"- current_json_max_bytes: `{s['current_json_max_bytes']}`",
        f"- current_json_source_count: `{s['current_json_source_count']}`",
        f"- current_json_skipped_large_count: `{s['current_json_skipped_large_count']}`",
        f"- current_json_skipped_large_size_human: `{s['current_json_skipped_large_size_human']}`",
        f"- candidate_count: `{s['candidate_count']}`",
        f"- candidate_size_human: `{s['candidate_size_human']}`",
        f"- delete_recommended_count: `{s['delete_recommended_count']}`",
        f"- delete_recommended_size_human: `{s['delete_recommended_size_human']}`",
        f"- top_rank_keep_count: `{s['top_rank_keep_count']}`",
        f"- top_rank_keep_size_human: `{s['top_rank_keep_size_human']}`",
        f"- referenced_keep_count: `{s['referenced_keep_count']}`",
        f"- referenced_keep_size_human: `{s['referenced_keep_size_human']}`",
        f"- review_required_count: `{s['review_required_count']}`",
        f"- review_required_size_human: `{s['review_required_size_human']}`",
        f"- cleanup_allowed_count: `{s['cleanup_allowed_count']}`",
        f"- delete_executed: `{s['delete_executed']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Top Delete Classes",
        "",
        "| cleanup_class | rows | size |",
        "| --- | ---: | ---: |",
    ]
    for row in payload["top_delete_classes"]:
        lines.append(
            f"| `{row['cleanup_class']}` | `{row['delete_recommended_count']}` | "
            f"`{row['delete_recommended_size_human']}` |"
        )
    lines.extend(["", "## Largest Delete-Recommended Paths", "", "| path | class | type | size |", "| --- | --- | --- | ---: |"])
    for row in payload["top_delete_paths"]:
        lines.append(f"| `{row['path']}` | `{row['cleanup_class']}` | `{row['path_type']}` | `{row['size_human']}` |")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a read-only cleanup manifest for local ligand-heavy run payloads.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--source-of-truth-json", default=DEFAULT_SOURCE_OF_TRUTH_JSON)
    parser.add_argument("--runs-dir", default="runs")
    parser.add_argument("--older-than-days", type=int, default=7)
    parser.add_argument("--current-json-max-bytes", type=int, default=DEFAULT_CURRENT_JSON_MAX_BYTES)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    root = Path(args.root)
    payload = build_ligand_heavy_run_cleanup_manifest(
        root=root,
        source_of_truth_json=args.source_of_truth_json,
        runs_dir=args.runs_dir,
        older_than_days=args.older_than_days,
        current_json_max_bytes=args.current_json_max_bytes,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["rows"])
    _write_markdown(args.out_md, payload, root=root)


if __name__ == "__main__":
    main()
