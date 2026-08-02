#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import heapq
import json
import socket
import time
from pathlib import Path
from typing import Any

from tools.accounting.build_storage_retention_manifest import _display, _human_size, _resolve
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "config/ligand_current_heavy_top_rank_compaction_current.json"
DEFAULT_OUT_CSV = "runs/ligand_current_heavy_top_rank_compaction_current.csv"
DEFAULT_OUT_MD = "docs/ligand_current_heavy_top_rank_compaction_current.md"
DEFAULT_RUNS_DIR = "runs"
DEFAULT_MIN_SIZE_BYTES = 10 * 1024 * 1024
DEFAULT_OLDER_THAN_DAYS = 7
DEFAULT_TOP_N = 50
APPROVAL_TOKEN = "APPROVE_LIGAND_CURRENT_HEAVY_TOP_RANK_COMPACTION"

CLAIM_BOUNDARY = (
    "Ligand current-heavy top-rank compaction only keeps compact top-ranking rows and path/size "
    "receipts before optionally deleting local generated CSV payloads. It does not run docking, "
    "change scores, approve claim promotion, delete input libraries, delete source files, mutate git "
    "history, or touch external state."
)

RAW_HEAVY_TOKENS = (
    "shadow_replay_scores",
    "replay_scores",
    "feature_cache",
    "stage3_refine_scores",
)

SKIP_LARGE_NAME_TOKENS = (
    "wetlab_broad_screen_compound_universe",
    "runs_artifact_inventory",
)

LIGAND_HEAVY_SCOPE_TOKENS = (
    "gpcr",
    "ligand",
    "htvs",
    "external_validation",
    "ion_trpv1",
    "kinase",
)

SCORE_COLUMN_PRIORITY = (
    "binding_score_composite_v7_htr2a_oprm1_drd2_weakbase_false_support_shadow",
    "binding_score_composite_v7_htr2a_oprm1_topology_pose_shadow",
    "binding_score_composite_v7_htr2a_topology_support_shadow",
    "binding_score_composite_v7_residual_shadow",
    "binding_score_composite_v7_residual_active",
    "binding_score_composite_v7",
    "base_score",
)

RETAIN_COLUMNS = (
    "queue_id",
    "target",
    "ligand_id",
    "ligand_smiles",
    "export_rank",
    "replica_idx",
    "is_binder",
    "reference_binding_kcal_mol",
    "base_score",
    "binding_score_composite_v7",
    "binding_score_composite_v7_residual_active",
    "binding_score_composite_v7_residual_shadow",
    "binding_score_composite_v7_htr2a_topology_support_shadow",
    "binding_score_composite_v7_htr2a_oprm1_topology_pose_shadow",
    "binding_score_composite_v7_htr2a_oprm1_drd2_weakbase_false_support_shadow",
    "binding_energy_mmpbsa_kcal_mol_proxy",
    "internal_refine_proxy_score",
    "binding_score_stronger_physics_v1",
    "physics_refinement_decision_bucket",
    "physics_refinement_confidence",
    "residual_shadow_delta",
    "residual_shadow_band",
    "feature_cache_status",
    "feature_cache_reason",
    "label_free_anchor_mode",
    "effective_label_free_anchor_mode",
    "mean_min_distance_A",
    "contact_fraction",
    "ligand_affinity_hint",
)


def _age_days(path: Path, *, now: float) -> float:
    try:
        return max(0.0, (now - path.stat().st_mtime) / 86_400)
    except OSError:
        return 0.0


def _is_candidate_name(name: str) -> bool:
    lower = name.lower()
    return (
        lower.endswith(".csv")
        and any(token in lower for token in LIGAND_HEAVY_SCOPE_TOKENS)
        and any(token in lower for token in RAW_HEAVY_TOKENS)
    )


def _skip_reason(path: Path) -> str:
    lower = path.name.lower()
    if any(token in lower for token in SKIP_LARGE_NAME_TOKENS):
        return "skipped_non_run_input_or_inventory_payload"
    if not lower.endswith(".csv"):
        return "skipped_non_csv_payload"
    if not any(token in lower for token in RAW_HEAVY_TOKENS):
        return "skipped_not_ligand_heavy_raw_score_or_feature_cache"
    if not any(token in lower for token in LIGAND_HEAVY_SCOPE_TOKENS):
        return "skipped_outside_current_ligand_heavy_scope"
    return ""


def _iter_candidate_paths(
    *,
    root: Path,
    runs_dir: str,
    min_size_bytes: int,
    older_than_days: int,
    now: float,
) -> tuple[list[Path], list[dict[str, Any]]]:
    runs_root = _resolve(runs_dir, root=root)
    candidates: list[Path] = []
    skipped: list[dict[str, Any]] = []
    if not runs_root.exists():
        return candidates, skipped
    for path in sorted(runs_root.iterdir()):
        if not path.is_file():
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size < min_size_bytes:
            continue
        age = _age_days(path, now=now)
        reason = _skip_reason(path)
        if _is_candidate_name(path.name) and age >= older_than_days:
            candidates.append(path)
            continue
        skipped.append(
            {
                "path": _display(path, root=root),
                "size_bytes": size,
                "size_human": _human_size(size),
                "age_days": round(age, 2),
                "reason": reason or "skipped_recent_or_unmatched_payload",
            }
        )
    return candidates, skipped


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _select_score_col(fieldnames: list[str] | None) -> str:
    if not fieldnames:
        return ""
    fields = set(fieldnames)
    for col in SCORE_COLUMN_PRIORITY:
        if col in fields:
            return col
    return ""


def _top_rank_output_path(path: Path, *, root: Path, top_n: int) -> Path:
    stem = path.stem
    if stem.endswith("_current"):
        stem = stem[: -len("_current")]
    return root / "runs" / f"{stem}_top_rank_retained_top{top_n}_current.csv"


def _compact_row(row: dict[str, str], *, rank: int, score_col: str, source_path: str) -> dict[str, Any]:
    compact: dict[str, Any] = {
        "source_path": source_path,
        "rank": rank,
        "score_col": score_col,
        "score_value": row.get(score_col, ""),
    }
    for col in RETAIN_COLUMNS:
        if col in row and row[col] != "":
            compact[col] = row[col]
    return compact


def _write_top_rows_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _compact_csv(path: Path, *, root: Path, top_n: int) -> dict[str, Any]:
    source_rel = _display(path, root=root)
    try:
        size = path.stat().st_size
    except OSError:
        size = 0
    row_count = 0
    invalid_score_count = 0
    score_col = ""
    heap: list[tuple[float, int, dict[str, str]]] = []
    fieldnames: list[str] | None = None
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = list(reader.fieldnames or [])
            score_col = _select_score_col(fieldnames)
            if not score_col:
                return {
                    "path": source_rel,
                    "size_bytes": size,
                    "size_human": _human_size(size),
                    "row_count": 0,
                    "score_col": "",
                    "top_rank_status": "blocked_missing_score_column",
                    "top_rank_output_csv": "",
                    "top_rows_retained_count": 0,
                    "top_rows": [],
                }
            for row in reader:
                row_count += 1
                score = _float_or_none(row.get(score_col))
                if score is None:
                    invalid_score_count += 1
                    continue
                entry = (-score, row_count, {str(k): str(v) for k, v in row.items()})
                if len(heap) < top_n:
                    heapq.heappush(heap, entry)
                elif entry > heap[0]:
                    heapq.heapreplace(heap, entry)
    except OSError as exc:
        return {
            "path": source_rel,
            "size_bytes": size,
            "size_human": _human_size(size),
            "row_count": row_count,
            "score_col": score_col,
            "top_rank_status": "blocked_read_failed",
            "error": str(exc),
            "top_rank_output_csv": "",
            "top_rows_retained_count": 0,
            "top_rows": [],
        }

    ordered = sorted(((-score, index, row) for score, index, row in heap), key=lambda item: (item[0], item[1]))
    top_rows = [
        _compact_row(row, rank=rank, score_col=score_col, source_path=source_rel)
        for rank, (_score, _index, row) in enumerate(ordered, start=1)
    ]
    out_csv = _top_rank_output_path(path, root=root, top_n=top_n)
    _write_top_rows_csv(out_csv, top_rows)
    return {
        "path": source_rel,
        "size_bytes": size,
        "size_human": _human_size(size),
        "row_count": row_count,
        "invalid_score_count": invalid_score_count,
        "score_col": score_col,
        "lower_better": True,
        "top_rank_status": "top_rank_retention_ready" if top_rows else "blocked_no_valid_scores",
        "top_rank_output_csv": _display(out_csv, root=root) if top_rows else "",
        "top_rows_retained_count": len(top_rows),
        "top_rows": top_rows,
    }


def _safe_delete_path(rel_path: str, *, root: Path) -> Path | None:
    if not rel_path or Path(rel_path).is_absolute():
        return None
    path = (root / rel_path).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return None
    if path.parts and ".git" in path.parts:
        return None
    if path.parent.name != "runs":
        return None
    if not path.name.endswith(".csv"):
        return None
    return path


def build_ligand_current_heavy_top_rank_compaction_receipt(
    *,
    root: str | Path = ROOT,
    runs_dir: str = DEFAULT_RUNS_DIR,
    min_size_bytes: int = DEFAULT_MIN_SIZE_BYTES,
    older_than_days: int = DEFAULT_OLDER_THAN_DAYS,
    top_n: int = DEFAULT_TOP_N,
    requested_host_label: str = "ubuntu-1",
    execute: bool = False,
    approval_token: str = "",
    now: float | None = None,
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    observed_now = time.time() if now is None else now
    candidates, skipped_large = _iter_candidate_paths(
        root=root_path,
        runs_dir=runs_dir,
        min_size_bytes=min_size_bytes,
        older_than_days=older_than_days,
        now=observed_now,
    )
    approval_token_valid = approval_token == APPROVAL_TOKEN
    delete_authorized = bool(execute and approval_token_valid)
    rows: list[dict[str, Any]] = []

    for path in candidates:
        row = _compact_csv(path, root=root_path, top_n=top_n)
        age = _age_days(path, now=observed_now)
        row["age_days"] = round(age, 2)
        delete_status = "not_requested"
        delete_error = ""
        safe_path = _safe_delete_path(str(row["path"]), root=root_path)
        if row.get("top_rank_status") != "top_rank_retention_ready":
            delete_status = "blocked_top_rank_not_retained"
        elif safe_path is None:
            delete_status = "blocked_unsafe_path"
        elif delete_authorized:
            try:
                if safe_path.exists():
                    safe_path.unlink()
                    delete_status = "deleted"
                else:
                    delete_status = "missing_before_delete"
            except OSError as exc:
                delete_status = "delete_failed"
                delete_error = str(exc)
        else:
            delete_status = "pending_delete_after_top_rank_retention"
        row.update(
            {
                "execute_requested": execute,
                "approval_token_valid": approval_token_valid,
                "delete_authorized": delete_authorized,
                "delete_status": delete_status,
                "delete_error": delete_error,
                "payload_write_allowed": False,
                "canonical_intake_promotion_allowed": False,
                "claim_promotion_allowed": False,
                "production_score_mutation_allowed": False,
                "external_state_mutated": False,
            }
        )
        rows.append(row)

    ready_rows = [row for row in rows if row.get("top_rank_status") == "top_rank_retention_ready"]
    deleted_rows = [row for row in rows if row.get("delete_status") == "deleted"]
    failed_rows = [row for row in rows if row.get("delete_status") in {"delete_failed", "blocked_unsafe_path"}]
    candidate_size = sum(int(row.get("size_bytes") or 0) for row in rows)
    deleted_size = sum(int(row.get("size_bytes") or 0) for row in deleted_rows)
    summary = {
        "packet_type": "ligand_current_heavy_top_rank_compaction_receipt",
        "status": (
            "ligand_current_heavy_top_rank_compaction_deleted_top_rank_retained"
            if delete_authorized and deleted_rows and not failed_rows
            else "ligand_current_heavy_top_rank_compaction_ready"
        ),
        "requested_host_label": requested_host_label,
        "observed_hostname": socket.gethostname(),
        "runs_dir": runs_dir,
        "min_size_bytes": min_size_bytes,
        "min_size_human": _human_size(min_size_bytes),
        "older_than_days": older_than_days,
        "top_n": top_n,
        "candidate_count": len(rows),
        "candidate_size_bytes": candidate_size,
        "candidate_size_human": _human_size(candidate_size),
        "top_rank_retention_ready_count": len(ready_rows),
        "top_rows_retained_count": sum(int(row.get("top_rows_retained_count") or 0) for row in rows),
        "skipped_large_count": len(skipped_large),
        "execute_requested": execute,
        "approval_token_required": APPROVAL_TOKEN,
        "approval_token_valid": approval_token_valid,
        "delete_authorized": delete_authorized,
        "deleted_count": len(deleted_rows),
        "deleted_size_bytes": deleted_size,
        "deleted_size_human": _human_size(deleted_size),
        "failed_count": len(failed_rows),
        "local_filesystem_mutated": bool(deleted_rows),
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Rerun the ligand-heavy cleanup manifest and readiness checks after compaction."
            if deleted_rows
            else "Review top-rank retained rows; run with --execute and approval token to delete original heavy CSVs."
        ),
    }
    return {"summary": summary, "rows": rows, "skipped_large_files": skipped_large}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    s = payload["summary"]
    lines = [
        "# Ligand Current Heavy Top-Rank Compaction",
        "",
        f"- status: `{s['status']}`",
        f"- requested_host_label: `{s['requested_host_label']}`",
        f"- observed_hostname: `{s['observed_hostname']}`",
        f"- candidate_count: `{s['candidate_count']}`",
        f"- candidate_size_human: `{s['candidate_size_human']}`",
        f"- top_rank_retention_ready_count: `{s['top_rank_retention_ready_count']}`",
        f"- top_rows_retained_count: `{s['top_rows_retained_count']}`",
        f"- skipped_large_count: `{s['skipped_large_count']}`",
        f"- execute_requested: `{s['execute_requested']}`",
        f"- approval_token_valid: `{s['approval_token_valid']}`",
        f"- deleted_count: `{s['deleted_count']}`",
        f"- deleted_size_human: `{s['deleted_size_human']}`",
        f"- failed_count: `{s['failed_count']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Compacted Payloads",
        "",
        "| path | rows | score | top rows | size | delete |",
        "| --- | ---: | --- | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['path']}` | `{row.get('row_count', 0)}` | `{row.get('score_col', '')}` | "
            f"`{row.get('top_rows_retained_count', 0)}` | `{row.get('size_human', '')}` | "
            f"`{row.get('delete_status', '')}` |"
        )
    if payload["skipped_large_files"]:
        lines.extend(["", "## Skipped Large Files", "", "| path | size | reason |", "| --- | ---: | --- |"])
        for row in payload["skipped_large_files"][:20]:
            lines.append(f"| `{row['path']}` | `{row['size_human']}` | `{row['reason']}` |")
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            s["claim_boundary"],
            "",
            "## Next Step",
            "",
            f"- {s['next_required_step']}",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compact old current-named ligand-heavy CSV payloads to top-rank receipts."
    )
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--runs-dir", default=DEFAULT_RUNS_DIR)
    parser.add_argument("--min-size-bytes", type=int, default=DEFAULT_MIN_SIZE_BYTES)
    parser.add_argument("--older-than-days", type=int, default=DEFAULT_OLDER_THAN_DAYS)
    parser.add_argument("--top-n", type=int, default=DEFAULT_TOP_N)
    parser.add_argument("--requested-host-label", default="ubuntu-1")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--approval-token", default="")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    root = Path(args.root)
    payload = build_ligand_current_heavy_top_rank_compaction_receipt(
        root=root,
        runs_dir=args.runs_dir,
        min_size_bytes=args.min_size_bytes,
        older_than_days=args.older_than_days,
        top_n=args.top_n,
        requested_host_label=args.requested_host_label,
        execute=args.execute,
        approval_token=args.approval_token,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(
        _resolve(args.out_csv, root=root),
        [
            {key: value for key, value in row.items() if key != "top_rows"}
            for row in payload["rows"]
        ],
    )
    _write_markdown(args.out_md, payload, root=root)


if __name__ == "__main__":
    main()
