#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUN_NAME = "product_gpcr_adrb2_after_approval"
DEFAULT_HEAVY_PAYLOAD_PATH = (
    "/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/"
    "product_gpcr_adrb2_after_approval/stage2_trajectory_frames"
)
DEFAULT_DRY_RUN_JSON = "runs/product_gpcr_adrb2_after_approval_external_heavy_cleanup_dry_run_current.json"
DEFAULT_RANKING_SUMMARY_JSON = "runs/product_gpcr_adrb2_after_approval_stage5_ranking_summary.json"
DEFAULT_RANKING_TOPK_CSV = "runs/product_gpcr_adrb2_after_approval_stage5_ranking_topk.csv"
DEFAULT_RANKING_UNIQUE_CSV = "runs/product_gpcr_adrb2_after_approval_stage5_ranking_unique.csv"
DEFAULT_REFINE_SHORTLIST_JSON = "runs/product_gpcr_adrb2_after_approval_stage3_refine_scores_shortlist.json"
DEFAULT_OUT_JSON = "config/ligand_external_heavy_top_rank_retention_product_gpcr_adrb2_current.json"
DEFAULT_OUT_MD = "docs/ligand_external_heavy_top_rank_retention_product_gpcr_adrb2_current.md"

CLAIM_BOUNDARY = (
    "External ligand-heavy top-rank retention only records compact ranking evidence before deleting local heavy "
    "trajectory payloads. It does not run docking, change ranking scores, approve commercial promotion, or "
    "claim wet-lab validation."
)


def _resolve(path_like: str | Path, *, root: Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _read_json(path_like: str | Path, *, root: Path) -> tuple[dict[str, Any], bool]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return {}, False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, True
    return payload if isinstance(payload, dict) else {}, True


def _human_size(size_bytes: int) -> str:
    value = float(max(size_bytes, 0))
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024.0 or unit == "TiB":
            return f"{value:.2f} {unit}"
        value /= 1024.0
    return f"{value:.2f} TiB"


def _sha256(path: Path) -> str:
    if not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_count(path: Path) -> int | None:
    if not path.exists():
        return None
    if path.is_file():
        return 1
    return sum(1 for item in path.rglob("*") if item.is_file())


def _du_size(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        output = subprocess.check_output(["du", "-sb", str(path)], text=True)
        return int(output.split()[0])
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        if path.is_file():
            return path.stat().st_size
        total = 0
        for item in path.rglob("*"):
            if item.is_file():
                total += item.stat().st_size
        return total


def _csv_rows(path_like: str | Path, *, root: Path, limit: int | None = None) -> list[dict[str, str]]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return []
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            rows.append({str(k): str(v) for k, v in row.items()})
            if limit is not None and len(rows) >= limit:
                break
    return rows


def _artifact_record(path_like: str | Path, *, root: Path) -> dict[str, Any]:
    path = _resolve(path_like, root=root)
    exists = path.is_file()
    size = path.stat().st_size if exists else 0
    return {
        "path": str(path_like),
        "exists": exists,
        "size_bytes": size,
        "size_human": _human_size(size),
        "sha256": _sha256(path) if exists else "",
    }


def _dry_run_row(dry_run: dict[str, Any], heavy_payload_path: str) -> dict[str, Any]:
    rows = dry_run.get("rows", [])
    if not isinstance(rows, list):
        return {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("path", "")) == heavy_payload_path:
            return row
    return rows[0] if rows and isinstance(rows[0], dict) else {}


def _metric_subset(summary: dict[str, Any]) -> dict[str, Any]:
    metrics = summary.get("metrics", {}) if isinstance(summary.get("metrics"), dict) else {}
    ci = summary.get("metrics_ci", {}) if isinstance(summary.get("metrics_ci"), dict) else {}
    names = (
        "roc_auc",
        "pr_auc",
        "ef1",
        "bedroc_alpha20",
        "brier",
        "ece_10bin",
        "positive_count",
        "score_unique_ratio",
        "score_tie_ratio",
        "score_mode_ratio",
        "spearman_ref_vs_score",
    )
    selected = {name: metrics.get(name) for name in names if name in metrics}
    selected_ci = {
        name: {"low": values.get("low"), "high": values.get("high"), "n": values.get("n")}
        for name, values in ci.items()
        if name in {"roc_auc", "pr_auc", "ef1", "bedroc_alpha20"} and isinstance(values, dict)
    }
    return selected | {"ci": selected_ci}


def build_receipt(
    *,
    root: str | Path = ROOT,
    run_name: str = DEFAULT_RUN_NAME,
    heavy_payload_path: str = DEFAULT_HEAVY_PAYLOAD_PATH,
    dry_run_json: str = DEFAULT_DRY_RUN_JSON,
    ranking_summary_json: str = DEFAULT_RANKING_SUMMARY_JSON,
    ranking_topk_csv: str = DEFAULT_RANKING_TOPK_CSV,
    ranking_unique_csv: str = DEFAULT_RANKING_UNIQUE_CSV,
    refine_shortlist_json: str = DEFAULT_REFINE_SHORTLIST_JSON,
    existing_receipt_json: str = DEFAULT_OUT_JSON,
    top_n: int = 50,
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    dry_run, dry_run_present = _read_json(dry_run_json, root=root_path)
    ranking_summary, ranking_summary_present = _read_json(ranking_summary_json, root=root_path)
    refine_shortlist, refine_shortlist_present = _read_json(refine_shortlist_json, root=root_path)
    existing, _ = _read_json(existing_receipt_json, root=root_path)
    previous_cleanup = existing.get("cleanup", {}) if isinstance(existing.get("cleanup"), dict) else {}
    dry_row = _dry_run_row(dry_run, heavy_payload_path)

    heavy_path = Path(heavy_payload_path)
    observed_exists = heavy_path.exists()
    observed_size = _du_size(heavy_path)
    pre_delete_size = int(dry_row.get("size_bytes") or previous_cleanup.get("pre_delete_size_bytes") or observed_size or 0)
    observed_count = _file_count(heavy_path)
    pre_delete_count = (
        observed_count
        if observed_count is not None
        else previous_cleanup.get("pre_delete_file_count")
    )
    top_rows = _csv_rows(ranking_unique_csv, root=root_path, limit=max(1, top_n))
    topk_rows = _csv_rows(ranking_topk_csv, root=root_path)
    artifacts = [
        _artifact_record(ranking_summary_json, root=root_path),
        _artifact_record(ranking_topk_csv, root=root_path),
        _artifact_record(ranking_unique_csv, root=root_path),
        _artifact_record(refine_shortlist_json, root=root_path),
    ]
    artifacts_ready = all(row["exists"] for row in artifacts)
    ranking_pass = bool(ranking_summary.get("pass"))
    dry_run_ready = dry_run_present and int(dry_run.get("summary", {}).get("planned_delete_count", 0) or 0) >= 1
    ready = artifacts_ready and ranking_summary_present and ranking_pass and bool(top_rows)
    status = "blocked_ligand_external_heavy_top_rank_retention"
    if ready and not observed_exists:
        status = "ligand_external_heavy_payload_deleted_top_rank_retained"
    elif ready and dry_run_ready:
        status = "ligand_external_heavy_top_rank_retention_ready_for_delete"

    cleanup = {
        "run_name": run_name,
        "heavy_payload_path": heavy_payload_path,
        "dry_run_json": dry_run_json,
        "dry_run_present": dry_run_present,
        "dry_run_status": dry_run.get("summary", {}).get("status", ""),
        "dry_run_planned_delete_count": int(dry_run.get("summary", {}).get("planned_delete_count", 0) or 0),
        "dry_run_row_status": dry_row.get("status", ""),
        "pre_delete_size_bytes": pre_delete_size,
        "pre_delete_size_human": _human_size(pre_delete_size),
        "pre_delete_file_count": pre_delete_count,
        "pre_delete_age_days": dry_row.get("age_days"),
        "observed_payload_exists": observed_exists,
        "observed_payload_size_bytes": observed_size,
        "observed_payload_size_human": _human_size(observed_size or 0),
        "deletion_status": "deleted_or_absent_after_compaction" if not observed_exists else "pending_delete",
    }
    ranking = {
        "ranking_summary_json": ranking_summary_json,
        "ranking_summary_present": ranking_summary_present,
        "ranking_pass": ranking_pass,
        "rows_eval": ranking_summary.get("rows_eval"),
        "eval_unique_keys": ranking_summary.get("eval_unique_keys"),
        "score_col": ranking_summary.get("score_col"),
        "lower_better": ranking_summary.get("lower_better"),
        "metrics": _metric_subset(ranking_summary),
        "topk": ranking_summary.get("topk", topk_rows),
        "topk_unique": ranking_summary.get("topk_unique", []),
        "top_rows_source": ranking_unique_csv,
        "top_rows_retained_count": len(top_rows),
        "top_rows": top_rows,
        "refine_shortlist_json": refine_shortlist_json,
        "refine_shortlist_present": refine_shortlist_present,
        "refine_selected_count": refine_shortlist.get("selected_count"),
    }
    summary = {
        "packet_type": "ligand_external_heavy_top_rank_retention_receipt",
        "status": status,
        "run_name": run_name,
        "heavy_payload_path": heavy_payload_path,
        "pre_delete_size_human": cleanup["pre_delete_size_human"],
        "pre_delete_file_count": pre_delete_count,
        "observed_payload_exists": observed_exists,
        "ranking_pass": ranking_pass,
        "retained_top_rows": len(top_rows),
        "retained_artifact_count": len([row for row in artifacts if row["exists"]]),
        "external_state_mutated": False,
        "local_external_filesystem_compaction": not observed_exists,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "No heavy payload action remains for this run; keep tracked config/docs receipt with top-rank evidence."
            if status == "ligand_external_heavy_payload_deleted_top_rank_retained"
            else "Execute the approved cleanup command for the heavy payload path, then regenerate this receipt."
        ),
    }
    return {"summary": summary, "cleanup": cleanup, "ranking": ranking, "retained_artifacts": artifacts}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    s = payload["summary"]
    c = payload["cleanup"]
    r = payload["ranking"]
    lines = [
        "# Ligand External Heavy Top-Rank Retention Receipt",
        "",
        f"- status: `{s['status']}`",
        f"- run_name: `{s['run_name']}`",
        f"- heavy_payload_path: `{s['heavy_payload_path']}`",
        f"- pre_delete_size_human: `{s['pre_delete_size_human']}`",
        f"- pre_delete_file_count: `{s['pre_delete_file_count']}`",
        f"- observed_payload_exists: `{s['observed_payload_exists']}`",
        f"- ranking_pass: `{s['ranking_pass']}`",
        f"- retained_top_rows: `{s['retained_top_rows']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Ranking Evidence",
        "",
        f"- summary_json: `{r['ranking_summary_json']}`",
        f"- top_rows_source: `{r['top_rows_source']}`",
        f"- rows_eval: `{r['rows_eval']}`",
        f"- eval_unique_keys: `{r['eval_unique_keys']}`",
        f"- roc_auc: `{r['metrics'].get('roc_auc')}`",
        f"- pr_auc: `{r['metrics'].get('pr_auc')}`",
        f"- ef1: `{r['metrics'].get('ef1')}`",
        "",
        "## Top-K",
        "",
        "| k | hit_rate | enrichment_factor | hits |",
        "| ---: | ---: | ---: | ---: |",
    ]
    for row in r.get("topk", []):
        if isinstance(row, dict):
            lines.append(
                f"| `{row.get('k')}` | `{row.get('hit_rate')}` | `{row.get('enrichment_factor')}` | `{row.get('hits')}` |"
            )
    lines.extend(
        [
            "",
            "## Cleanup",
            "",
            f"- dry_run_json: `{c['dry_run_json']}`",
            f"- dry_run_status: `{c['dry_run_status']}`",
            f"- dry_run_planned_delete_count: `{c['dry_run_planned_delete_count']}`",
            f"- deletion_status: `{c['deletion_status']}`",
            "",
            "## Retained Artifacts",
            "",
        ]
    )
    for row in payload["retained_artifacts"]:
        lines.append(f"- `{row['path']}` (`{row['size_human']}`, sha256 `{row['sha256'][:12]}`)")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a tracked top-rank retention receipt for an external ligand-heavy payload.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--run-name", default=DEFAULT_RUN_NAME)
    parser.add_argument("--heavy-payload-path", default=DEFAULT_HEAVY_PAYLOAD_PATH)
    parser.add_argument("--dry-run-json", default=DEFAULT_DRY_RUN_JSON)
    parser.add_argument("--ranking-summary-json", default=DEFAULT_RANKING_SUMMARY_JSON)
    parser.add_argument("--ranking-topk-csv", default=DEFAULT_RANKING_TOPK_CSV)
    parser.add_argument("--ranking-unique-csv", default=DEFAULT_RANKING_UNIQUE_CSV)
    parser.add_argument("--refine-shortlist-json", default=DEFAULT_REFINE_SHORTLIST_JSON)
    parser.add_argument("--top-n", type=int, default=50)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    root = Path(args.root).resolve()
    payload = build_receipt(
        root=root,
        run_name=args.run_name,
        heavy_payload_path=args.heavy_payload_path,
        dry_run_json=args.dry_run_json,
        ranking_summary_json=args.ranking_summary_json,
        ranking_topk_csv=args.ranking_topk_csv,
        ranking_unique_csv=args.ranking_unique_csv,
        refine_shortlist_json=args.refine_shortlist_json,
        existing_receipt_json=args.out_json,
        top_n=args.top_n,
    )
    _write_json(args.out_json, payload, root=root)
    _write_markdown(args.out_md, payload, root=root)


if __name__ == "__main__":
    main()
