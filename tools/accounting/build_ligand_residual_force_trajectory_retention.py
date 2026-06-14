#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from tools.accounting.apply_ligand_heavy_run_cleanup_manifest import APPROVAL_TOKEN
from tools.accounting.build_storage_retention_manifest import _display, _human_size, _resolve
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STAGE2_ROOT = "runs/residual_force_trajectory_regeneration_current/stage2_trajectory_frames"
DEFAULT_QUEUE_CSV = "runs/residual_force_trajectory_regeneration_queue_current.csv"
DEFAULT_QUEUE_JSON = "runs/residual_force_trajectory_regeneration_queue_current.json"
DEFAULT_MANIFEST_CSV = "runs/residual_force_trajectory_regeneration_current_manifest.csv"
DEFAULT_SUMMARY_JSON = "runs/residual_force_trajectory_regeneration_current_summary.json"
DEFAULT_SUMMARY_MD = "runs/residual_force_trajectory_regeneration_current_summary.md"
DEFAULT_PROGRESS_JSON = "runs/residual_force_trajectory_regeneration_current_progress.json"
DEFAULT_EXECUTION_PROBE_JSON = "runs/residual_force_trajectory_regeneration_execution_probe_current.json"
DEFAULT_TARGET_TAIL_CSV = (
    "runs/residual_force_trajectory_regeneration_current/stage2_trajectory_frames_target_tail.csv"
)
DEFAULT_OUT_JSON = "config/ligand_residual_force_trajectory_retention_current.json"
DEFAULT_OUT_MD = "docs/ligand_residual_force_trajectory_retention_current.md"
DEFAULT_DELETE_MANIFEST_JSON = "runs/ligand_residual_force_trajectory_cleanup_manifest_current.json"
DEFAULT_DELETE_MANIFEST_CSV = "runs/ligand_residual_force_trajectory_cleanup_manifest_current.csv"
DEFAULT_EXECUTION_JSON = "runs/ligand_residual_force_trajectory_cleanup_execution_current.json"

EVIDENCE_PATHS = (
    DEFAULT_QUEUE_CSV,
    DEFAULT_QUEUE_JSON,
    DEFAULT_MANIFEST_CSV,
    DEFAULT_SUMMARY_JSON,
    DEFAULT_SUMMARY_MD,
    DEFAULT_PROGRESS_JSON,
    DEFAULT_EXECUTION_PROBE_JSON,
    DEFAULT_TARGET_TAIL_CSV,
)

CLAIM_BOUNDARY = (
    "Ligand residual-force trajectory retention records compact target/ranking evidence for the regenerated "
    "NPZ bundles, then prepares an approval-gated manifest for deleting raw stage2 trajectory NPZ files. It "
    "does not change scientific claims, delete retained queue/summary/manifest evidence, touch git history, "
    "upload, push, run docking, or train models."
)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    except OSError:
        return []


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _norm_path(value: str) -> str:
    return str(value or "").strip().lstrip("./")


def _npz_candidates(stage2_root: Path, *, root: Path) -> list[Path]:
    if not stage2_root.exists():
        return []
    rows: list[Path] = []
    for path in sorted(stage2_root.rglob("*.npz")):
        if path.is_file():
            try:
                path.resolve().relative_to(root)
            except ValueError:
                continue
            rows.append(path)
    return rows


def _index_by(rows: list[dict[str, str]], key: str) -> dict[str, dict[str, str]]:
    indexed: dict[str, dict[str, str]] = {}
    for row in rows:
        value = _norm_path(row.get(key, ""))
        if value and value not in indexed:
            indexed[value] = row
    return indexed


def _source_stage3_files(queue_rows: list[dict[str, str]], *, root: Path) -> list[str]:
    seen: set[str] = set()
    rows: list[str] = []
    for row in queue_rows:
        rel = _norm_path(row.get("source_stage3_csv", ""))
        if not rel or rel in seen:
            continue
        seen.add(rel)
        if _resolve(rel, root=root).is_file():
            rows.append(rel)
    return rows


def _evidence_files(queue_rows: list[dict[str, str]], *, root: Path) -> list[str]:
    files: list[str] = []
    for rel in EVIDENCE_PATHS:
        if _resolve(rel, root=root).is_file():
            files.append(rel)
    files.extend(_source_stage3_files(queue_rows, root=root))
    return sorted(dict.fromkeys(files))


def _target_tail_rows(path: Path) -> list[dict[str, str]]:
    return _read_csv(path)


def _merge_manifest_queue_rows(
    manifest_rows: list[dict[str, str]],
    queue_rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    by_expected = _index_by(queue_rows, "expected_regenerated_trajectory_npz")
    by_queue = _index_by(queue_rows, "queue_id")
    merged: list[dict[str, Any]] = []
    for row in manifest_rows:
        generated_npz = _norm_path(row.get("generated_npz", ""))
        queue_id = str(row.get("queue_id") or "")
        queue = by_expected.get(generated_npz) or by_queue.get(queue_id) or {}
        merged.append({"manifest": row, "queue": queue})
    return merged


def _retained_top_rank_rows(
    manifest_rows: list[dict[str, str]],
    queue_rows: list[dict[str, str]],
    *,
    topk_per_target: int,
) -> list[dict[str, Any]]:
    best_by_target_ligand: dict[tuple[str, str], dict[str, Any]] = {}
    for item in _merge_manifest_queue_rows(manifest_rows, queue_rows):
        manifest = item["manifest"]
        queue = item["queue"]
        target = str(manifest.get("target") or queue.get("target") or "")
        ligand_id = str(manifest.get("ligand_id") or queue.get("ligand_id") or "")
        if not target or not ligand_id:
            continue
        compact = {
            "rank_source": "ligand_affinity_hint_desc_then_quality_score_desc",
            "target": target,
            "ligand_id": ligand_id,
            "ligand_smiles": queue.get("ligand_smiles", ""),
            "queue_id": manifest.get("queue_id") or queue.get("queue_id", ""),
            "original_queue_id": queue.get("original_queue_id", ""),
            "replica_idx": queue.get("replica_idx", ""),
            "ligand_affinity_hint": _as_float(manifest.get("affinity_hint") or queue.get("ligand_affinity_hint")),
            "quality_score": _as_float(manifest.get("quality_score")),
            "stability_score": _as_float(manifest.get("stability_score")),
            "contact_fraction": _as_float(manifest.get("contact_fraction")),
            "contact_fraction_6A": _as_float(manifest.get("contact_fraction_6A")),
            "mean_min_distance_A": _as_float(manifest.get("mean_min_distance_A")),
            "binding_energy_proxy": _as_float(manifest.get("binding_energy_proxy")),
            "binding_energy_mmpbsa_kcal_mol_proxy": _as_float(
                manifest.get("binding_energy_mmpbsa_kcal_mol_proxy")
            ),
            "frames_written": _as_int(manifest.get("frames_written")),
            "backend": manifest.get("backend", ""),
            "source_stage3_csv": queue.get("source_stage3_csv", ""),
            "generated_npz": manifest.get("generated_npz", ""),
            "original_trajectory_npz": queue.get("original_trajectory_npz", ""),
            "native_pdb_path": queue.get("native_pdb_path", ""),
        }
        key = (target, ligand_id)
        current = best_by_target_ligand.get(key)
        if current is None or _rank_sort_key(compact) < _rank_sort_key(current):
            best_by_target_ligand[key] = compact

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in best_by_target_ligand.values():
        grouped[str(row["target"])].append(row)

    retained: list[dict[str, Any]] = []
    for target in sorted(grouped):
        ranked = sorted(grouped[target], key=_rank_sort_key)
        for idx, row in enumerate(ranked[:topk_per_target], start=1):
            out = dict(row)
            out["export_rank"] = idx
            retained.append(out)
    return retained


def _rank_sort_key(row: dict[str, Any]) -> tuple[float, float, float, str]:
    return (
        -_as_float(row.get("ligand_affinity_hint")),
        -_as_float(row.get("quality_score")),
        _as_float(row.get("mean_min_distance_A"), default=999999.0),
        str(row.get("ligand_id") or ""),
    )


def _delete_manifest_rows(
    npz_files: list[Path],
    manifest_rows: list[dict[str, str]],
    queue_rows: list[dict[str, str]],
    *,
    root: Path,
    preserved_evidence: list[str],
) -> list[dict[str, Any]]:
    by_generated = _index_by(manifest_rows, "generated_npz")
    by_expected = _index_by(queue_rows, "expected_regenerated_trajectory_npz")
    rows: list[dict[str, Any]] = []
    for path in npz_files:
        rel = _display(path, root=root)
        manifest = by_generated.get(rel, {})
        queue = by_expected.get(rel, {})
        size = path.stat().st_size
        rows.append(
            {
                "path": rel,
                "path_type": "file",
                "size_bytes": size,
                "size_human": _human_size(size),
                "cleanup_class": "residual_force_regenerated_npz_bundle",
                "disposition": "delete_after_residual_force_compact_retention_record",
                "delete_recommended": True,
                "target": manifest.get("target") or queue.get("target", ""),
                "ligand_id": manifest.get("ligand_id") or queue.get("ligand_id", ""),
                "queue_id": manifest.get("queue_id") or queue.get("queue_id", ""),
                "frames_written": manifest.get("frames_written", ""),
                "backend": manifest.get("backend", ""),
                "preserved_evidence_count": len(preserved_evidence),
                "preserved_evidence": ";".join(preserved_evidence[:30]),
                "delete_executed": False,
                "external_state_mutated": False,
                "reason": "Compact residual-force queue, manifest, summary, target-tail, and top-ranked ligand records are retained.",
            }
        )
    return rows


def _target_summaries(manifest_rows: list[dict[str, str]], delete_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    count_by_target: Counter[str] = Counter()
    frames_by_target: defaultdict[str, list[int]] = defaultdict(list)
    size_by_target: Counter[str] = Counter()
    for row in manifest_rows:
        target = str(row.get("target") or "unknown")
        count_by_target[target] += 1
        frames_by_target[target].append(_as_int(row.get("frames_written")))
    for row in delete_rows:
        target = str(row.get("target") or "unknown")
        size_by_target[target] += int(row.get("size_bytes") or 0)

    rows: list[dict[str, Any]] = []
    for target in sorted(count_by_target):
        frames = frames_by_target[target]
        rows.append(
            {
                "target": target,
                "manifest_row_count": count_by_target[target],
                "delete_recommended_npz_size_bytes": size_by_target[target],
                "delete_recommended_npz_size_human": _human_size(size_by_target[target]),
                "frames_written_min": min(frames) if frames else 0,
                "frames_written_mean": sum(frames) / len(frames) if frames else 0.0,
                "frames_written_max": max(frames) if frames else 0,
            }
        )
    return rows


def _existing_delete_manifest_rows(path: Path) -> list[dict[str, Any]]:
    payload = _read_json(path)
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _execution_summary(path: Path) -> dict[str, Any]:
    payload = _read_json(path)
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def build_ligand_residual_force_trajectory_retention(
    *,
    root: str | Path = ROOT,
    stage2_root: str | Path = DEFAULT_STAGE2_ROOT,
    queue_csv: str | Path = DEFAULT_QUEUE_CSV,
    manifest_csv: str | Path = DEFAULT_MANIFEST_CSV,
    summary_json: str | Path = DEFAULT_SUMMARY_JSON,
    target_tail_csv: str | Path = DEFAULT_TARGET_TAIL_CSV,
    delete_manifest_json: str | Path = DEFAULT_DELETE_MANIFEST_JSON,
    execution_json: str | Path = DEFAULT_EXECUTION_JSON,
    topk_per_target: int = 20,
) -> tuple[dict[str, Any], dict[str, Any]]:
    root_path = Path(root).resolve()
    stage2_path = _resolve(stage2_root, root=root_path)
    queue_rows = _read_csv(_resolve(queue_csv, root=root_path))
    manifest_rows = _read_csv(_resolve(manifest_csv, root=root_path))
    run_summary = _read_json(_resolve(summary_json, root=root_path))
    tail_rows = _target_tail_rows(_resolve(target_tail_csv, root=root_path))
    current_npz_files = _npz_candidates(stage2_path, root=root_path)
    preserved_evidence = _evidence_files(queue_rows, root=root_path)
    delete_rows = _delete_manifest_rows(
        current_npz_files,
        manifest_rows,
        queue_rows,
        root=root_path,
        preserved_evidence=preserved_evidence,
    )
    existing_manifest_rows = _existing_delete_manifest_rows(_resolve(delete_manifest_json, root=root_path))
    execution = _execution_summary(_resolve(execution_json, root=root_path))
    retained_top_rank = _retained_top_rank_rows(
        manifest_rows,
        queue_rows,
        topk_per_target=topk_per_target,
    )
    target_summaries = _target_summaries(manifest_rows, delete_rows or existing_manifest_rows)

    active_delete_rows = delete_rows if delete_rows else existing_manifest_rows
    active_delete_count = len(active_delete_rows)
    active_delete_size = sum(int(row.get("size_bytes") or 0) for row in active_delete_rows)
    deleted_count = int(execution.get("deleted_count") or 0)
    failed_count = int(execution.get("failed_count") or 0)
    delete_executed = bool(execution.get("delete_executed"))
    post_delete_count = len(current_npz_files)
    blocked_reasons: list[str] = []
    if not manifest_rows:
        blocked_reasons.append("residual_force_manifest_csv_missing_or_empty")
    if not queue_rows:
        blocked_reasons.append("residual_force_queue_csv_missing_or_empty")
    if not retained_top_rank:
        blocked_reasons.append("retained_top_rank_rows_missing")
    if not preserved_evidence:
        blocked_reasons.append("preserved_evidence_files_missing")

    if delete_executed and failed_count == 0 and post_delete_count == 0:
        status = "ligand_residual_force_trajectory_compaction_complete"
    elif blocked_reasons:
        status = "blocked_ligand_residual_force_trajectory_compaction"
    elif delete_rows:
        status = "ligand_residual_force_trajectory_compaction_ready"
    elif not current_npz_files:
        status = "ligand_residual_force_trajectory_compaction_noop"
    else:
        status = "blocked_ligand_residual_force_trajectory_compaction"

    summary = {
        "packet_type": "ligand_residual_force_trajectory_retention",
        "status": status,
        "generated_at_local": datetime.now().replace(microsecond=0).isoformat(),
        "stage2_root": _display(stage2_path, root=root_path),
        "queue_csv": _display(_resolve(queue_csv, root=root_path), root=root_path),
        "manifest_csv": _display(_resolve(manifest_csv, root=root_path), root=root_path),
        "summary_json": _display(_resolve(summary_json, root=root_path), root=root_path),
        "target_tail_csv": _display(_resolve(target_tail_csv, root=root_path), root=root_path),
        "queue_rows": len(queue_rows),
        "manifest_rows": len(manifest_rows),
        "run_summary_ok_rows": run_summary.get("ok_rows", ""),
        "run_summary_failed_rows": run_summary.get("failed_rows", ""),
        "backend_counts": run_summary.get("backend_counts", {}),
        "current_npz_count": len(current_npz_files),
        "current_npz_size_bytes": sum(path.stat().st_size for path in current_npz_files),
        "current_npz_size_human": _human_size(sum(path.stat().st_size for path in current_npz_files)),
        "delete_recommended_count": active_delete_count,
        "delete_recommended_size_bytes": active_delete_size,
        "delete_recommended_size_human": _human_size(active_delete_size),
        "retained_top_rank_count": len(retained_top_rank),
        "topk_per_target": topk_per_target,
        "target_summary_count": len(target_summaries),
        "target_tail_row_count": len(tail_rows),
        "preserved_evidence_file_count": len(preserved_evidence),
        "delete_manifest_json": _display(_resolve(delete_manifest_json, root=root_path), root=root_path),
        "delete_manifest_csv": DEFAULT_DELETE_MANIFEST_CSV,
        "approval_token_required": APPROVAL_TOKEN,
        "execution_json": _display(_resolve(execution_json, root=root_path), root=root_path),
        "delete_executed": delete_executed,
        "deleted_count": deleted_count,
        "deleted_size_bytes": int(execution.get("deleted_size_bytes") or 0),
        "deleted_size_human": execution.get("deleted_size_human", _human_size(0)),
        "failed_count": failed_count,
        "post_delete_npz_present_count": post_delete_count,
        "blocked_reasons": blocked_reasons,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "No further cleanup action for this residual-force trajectory set; compact evidence is retained."
            if status == "ligand_residual_force_trajectory_compaction_complete"
            else "Run the approval-gated ligand heavy cleanup executor on the generated delete manifest."
            if status == "ligand_residual_force_trajectory_compaction_ready"
            else "Review blocked reasons before deleting regenerated trajectory NPZ files."
        ),
    }
    retention_payload = {
        "summary": summary,
        "target_summaries": target_summaries,
        "target_tail": tail_rows,
        "preserved_evidence_files": preserved_evidence,
        "retained_top_rank": retained_top_rank,
    }
    manifest_payload = {
        "summary": {
            "packet_type": "ligand_residual_force_trajectory_delete_manifest",
            "status": "ligand_heavy_run_cleanup_manifest_ready" if delete_rows else "ligand_heavy_run_cleanup_manifest_noop",
            "source_retention_json": DEFAULT_OUT_JSON,
            "delete_recommended_count": len(delete_rows),
            "delete_recommended_size_bytes": sum(int(row["size_bytes"]) for row in delete_rows),
            "delete_recommended_size_human": _human_size(sum(int(row["size_bytes"]) for row in delete_rows)),
            "delete_executed": False,
            "external_state_mutated": False,
            "claim_boundary": CLAIM_BOUNDARY,
        },
        "rows": delete_rows,
    }
    return retention_payload, manifest_payload


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    s = payload["summary"]
    lines = [
        "# Ligand Residual Force Trajectory Retention",
        "",
        f"- status: `{s['status']}`",
        f"- stage2_root: `{s['stage2_root']}`",
        f"- queue_rows: `{s['queue_rows']}`",
        f"- manifest_rows: `{s['manifest_rows']}`",
        f"- current_npz_count: `{s['current_npz_count']}`",
        f"- current_npz_size_human: `{s['current_npz_size_human']}`",
        f"- delete_recommended_count: `{s['delete_recommended_count']}`",
        f"- delete_recommended_size_human: `{s['delete_recommended_size_human']}`",
        f"- retained_top_rank_count: `{s['retained_top_rank_count']}`",
        f"- preserved_evidence_file_count: `{s['preserved_evidence_file_count']}`",
        f"- delete_manifest_json: `{s['delete_manifest_json']}`",
        f"- approval_token_required: `{s['approval_token_required']}`",
        f"- delete_executed: `{s['delete_executed']}`",
        f"- deleted_count: `{s['deleted_count']}`",
        f"- deleted_size_human: `{s['deleted_size_human']}`",
        f"- failed_count: `{s['failed_count']}`",
        f"- post_delete_npz_present_count: `{s['post_delete_npz_present_count']}`",
        "",
        "## Target Summary",
        "",
        "| target | manifest rows | retained size | frames min | frames mean | frames max |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["target_summaries"]:
        lines.append(
            f"| `{row['target']}` | `{row['manifest_row_count']}` | "
            f"`{row['delete_recommended_npz_size_human']}` | `{row['frames_written_min']}` | "
            f"`{row['frames_written_mean']}` | `{row['frames_written_max']}` |"
        )
    lines.extend(
        [
            "",
            "## Top Retained Records",
            "",
            "| target | rank | ligand_id | affinity_hint | quality | frames | generated_npz |",
            "| --- | ---: | --- | ---: | ---: | ---: | --- |",
        ]
    )
    for row in payload["retained_top_rank"][:30]:
        lines.append(
            f"| `{row['target']}` | `{row['export_rank']}` | `{row['ligand_id']}` | "
            f"`{row['ligand_affinity_hint']}` | `{row['quality_score']}` | "
            f"`{row['frames_written']}` | `{row['generated_npz']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compact residual-force ligand trajectory evidence.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--stage2-root", default=DEFAULT_STAGE2_ROOT)
    parser.add_argument("--queue-csv", default=DEFAULT_QUEUE_CSV)
    parser.add_argument("--manifest-csv", default=DEFAULT_MANIFEST_CSV)
    parser.add_argument("--summary-json", default=DEFAULT_SUMMARY_JSON)
    parser.add_argument("--target-tail-csv", default=DEFAULT_TARGET_TAIL_CSV)
    parser.add_argument("--topk-per-target", type=int, default=20)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--delete-manifest-json", default=DEFAULT_DELETE_MANIFEST_JSON)
    parser.add_argument("--delete-manifest-csv", default=DEFAULT_DELETE_MANIFEST_CSV)
    parser.add_argument("--execution-json", default=DEFAULT_EXECUTION_JSON)
    parser.add_argument("--no-delete-manifest", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    root = Path(args.root)
    retention_payload, manifest_payload = build_ligand_residual_force_trajectory_retention(
        root=root,
        stage2_root=args.stage2_root,
        queue_csv=args.queue_csv,
        manifest_csv=args.manifest_csv,
        summary_json=args.summary_json,
        target_tail_csv=args.target_tail_csv,
        delete_manifest_json=args.delete_manifest_json,
        execution_json=args.execution_json,
        topk_per_target=args.topk_per_target,
    )
    _write_json(args.out_json, retention_payload, root=root)
    _write_markdown(args.out_md, retention_payload, root=root)
    if not args.no_delete_manifest:
        _write_json(args.delete_manifest_json, manifest_payload, root=root)
        write_csv_rows(_resolve(args.delete_manifest_csv, root=root), manifest_payload["rows"])


if __name__ == "__main__":
    main()
