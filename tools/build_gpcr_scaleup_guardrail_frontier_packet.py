#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import glob
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_CANDIDATE_GLOBS = [
    "runs/external_validation_*100k*set1_core_blind_gpcr_core_full_p0_n100000_r1_stage5_ranking_rows.csv",
    "runs/archive/runs_artifact_inventory_root_archive_current/external_validation_*100k*set1_core_blind_gpcr_core_full_p0_n100000_r1_stage5_ranking_rows.csv",
]
DEFAULT_OUT_JSON = "runs/gpcr_scaleup_guardrail_frontier_packet_current.json"
DEFAULT_OUT_CSV = "runs/gpcr_scaleup_guardrail_frontier_packet_current.csv"
DEFAULT_OUT_MD = "runs/gpcr_scaleup_guardrail_frontier_packet_current.md"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _is_positive(row: dict[str, Any]) -> bool:
    return str(row.get("is_binder", "")).strip().lower() in {"1", "true", "yes"}


def _positive_ranks(rows: list[dict[str, Any]]) -> list[int]:
    return [rank for rank, row in enumerate(rows, start=1) if _is_positive(row)]


def _average_precision(positive_ranks: list[int]) -> float:
    if not positive_ranks:
        return 0.0
    return float(sum((index + 1) / rank for index, rank in enumerate(positive_ranks)) / len(positive_ranks))


def _topk_hit_rate(positive_ranks: list[int], *, topk_k: int) -> float:
    if topk_k <= 0:
        return 0.0
    return float(sum(1 for rank in positive_ranks if rank <= topk_k) / topk_k)


def _candidate_id(path: Path) -> str:
    suffix = "_set1_core_blind_gpcr_core_full_p0_n100000_r1_stage5_ranking_rows"
    return path.stem.removesuffix(suffix).removeprefix("external_validation_")


def _promotion_tier(path: Path, claim_safe: bool) -> str:
    name = path.name.lower()
    if not claim_safe:
        return "failed_guardrail"
    if "family_balanced" in name or "coverage" in name or "beta_blocker_rescue" in name:
        return "family_balanced_recovery_candidate"
    if "adrb2_pharmacophore" in name:
        return "target_pharmacophore_context_only"
    return "claim_safe_candidate"


def _promotion_priority(tier: str) -> int:
    return {
        "family_balanced_recovery_candidate": 4,
        "claim_safe_candidate": 3,
        "target_pharmacophore_context_only": 2,
        "failed_guardrail": 1,
    }.get(tier, 0)


def _discover_candidates(globs: list[str]) -> list[Path]:
    paths: dict[str, Path] = {}
    for pattern in globs:
        for item in glob.glob(str(_resolve(pattern))):
            path = Path(item).resolve()
            if path.exists():
                paths[str(path)] = path
    return sorted(paths.values())


def _row_for(path: Path, *, pr_auc_min: float, topk_k: int, topk_hit_rate_min: float) -> dict[str, Any]:
    rows = _read_csv(path)
    positive_ranks = _positive_ranks(rows)
    pr_auc = _average_precision(positive_ranks)
    topk_hit_rate = _topk_hit_rate(positive_ranks, topk_k=topk_k)
    claim_safe = bool(pr_auc >= pr_auc_min and topk_hit_rate >= topk_hit_rate_min)
    tier = _promotion_tier(path, claim_safe)
    rel_path = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
    return {
        "candidate_id": _candidate_id(path),
        "artifact": str(rel_path),
        "row_count": len(rows),
        "positive_count": len(positive_ranks),
        "positive_ranks": positive_ranks,
        "top20_binder_count": sum(1 for rank in positive_ranks if rank <= topk_k),
        "last_positive_rank": positive_ranks[-1] if positive_ranks else 0,
        "pr_auc": pr_auc,
        "topk_k": topk_k,
        "topk_hit_rate": topk_hit_rate,
        "pr_auc_min": pr_auc_min,
        "topk_hit_rate_min": topk_hit_rate_min,
        "claim_safe": claim_safe,
        "promotion_tier": tier,
        "promotion_priority": _promotion_priority(tier),
    }


def build_payload(
    *,
    candidate_paths: list[str] | None = None,
    candidate_globs: list[str] | None = None,
    pr_auc_min: float = 0.55,
    topk_k: int = 20,
    topk_hit_rate_min: float = 0.2,
) -> dict[str, Any]:
    paths = (
        [_resolve(path) for path in candidate_paths or []]
        if candidate_paths
        else _discover_candidates(candidate_globs or DEFAULT_CANDIDATE_GLOBS)
    )
    rows = [
        _row_for(path, pr_auc_min=pr_auc_min, topk_k=topk_k, topk_hit_rate_min=topk_hit_rate_min)
        for path in paths
        if path.exists()
    ]
    rows.sort(
        key=lambda row: (
            int(row.get("promotion_priority", 0)),
            float(row.get("pr_auc", 0.0)),
            float(row.get("topk_hit_rate", 0.0)),
            -int(row.get("last_positive_rank", 0)),
            str(row.get("candidate_id", "")),
        ),
        reverse=True,
    )
    top = rows[0] if rows else {}
    claim_safe = bool(top.get("claim_safe")) and str(top.get("promotion_tier")) != "target_pharmacophore_context_only"
    summary = {
        "packet_ready": True,
        "packet_artifact": DEFAULT_OUT_MD,
        "candidate_count": len(rows),
        "claim_safe_candidate_count": sum(1 for row in rows if bool(row.get("claim_safe"))),
        "promotion_allowed_candidate_count": sum(
            1
            for row in rows
            if bool(row.get("claim_safe"))
            and str(row.get("promotion_tier")) != "target_pharmacophore_context_only"
        ),
        "claim_safe": claim_safe,
        "claim_safe_status": "guardrail_recovered_candidate_available" if claim_safe else "regression_guardrail_failed",
        "top_candidate_id": str(top.get("candidate_id", "")),
        "top_candidate_artifact": str(top.get("artifact", "")),
        "top_candidate_promotion_tier": str(top.get("promotion_tier", "")),
        "top_candidate_pr_auc": top.get("pr_auc"),
        "top_candidate_topk_hit_rate": top.get("topk_hit_rate"),
        "top_candidate_top20_binder_count": top.get("top20_binder_count"),
        "top_candidate_last_positive_rank": top.get("last_positive_rank"),
        "thresholds": {
            "pr_auc_min": pr_auc_min,
            "topk_k": topk_k,
            "topk_hit_rate_min": topk_hit_rate_min,
        },
        "next_required_step": (
            "Promote the family-balanced GPCR 100k recovery candidate into the ligand scale-up benchmark summary, "
            "then rerun suite status and keep equal-size/1M packaging as separate scale-up completion work."
            if claim_safe
            else "No promotion-allowed GPCR 100k candidate passes the PR-AUC/top20 guardrail; continue score-family diagnostics."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "candidate_id",
        "artifact",
        "promotion_tier",
        "claim_safe",
        "pr_auc",
        "topk_hit_rate",
        "top20_binder_count",
        "last_positive_rank",
        "positive_count",
        "row_count",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _fmt(value: Any) -> str:
    if isinstance(value, float) and math.isfinite(value):
        return f"{value:.4f}"
    return str(value if value is not None else "")


def _write_md(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# GPCR Scale-up Guardrail Frontier Packet",
        "",
        f"- packet_ready: `{s['packet_ready']}`",
        f"- candidate_count: `{s['candidate_count']}`",
        f"- claim_safe_candidate_count: `{s['claim_safe_candidate_count']}`",
        f"- promotion_allowed_candidate_count: `{s['promotion_allowed_candidate_count']}`",
        f"- claim_safe: `{s['claim_safe']}`",
        f"- claim_safe_status: `{s['claim_safe_status']}`",
        f"- top_candidate_id: `{s['top_candidate_id']}`",
        f"- top_candidate_promotion_tier: `{s['top_candidate_promotion_tier']}`",
        f"- top_candidate_pr_auc: `{_fmt(s['top_candidate_pr_auc'])}`",
        f"- top_candidate_topk_hit_rate: `{_fmt(s['top_candidate_topk_hit_rate'])}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Candidates",
        "",
        "| candidate_id | promotion_tier | claim_safe | pr_auc | top20_hit_rate | top20_binders | last_positive_rank |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['candidate_id']}` | `{row['promotion_tier']}` | `{row['claim_safe']}` | "
            f"{_fmt(row['pr_auc'])} | {_fmt(row['topk_hit_rate'])} | {row['top20_binder_count']} | {row['last_positive_rank']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build GPCR 100k scale-up guardrail candidate frontier packet.")
    parser.add_argument("--candidate-csv", action="append", default=[])
    parser.add_argument("--candidate-glob", action="append", default=[])
    parser.add_argument("--pr-auc-min", type=float, default=0.55)
    parser.add_argument("--topk-k", type=int, default=20)
    parser.add_argument("--topk-hit-rate-min", type=float, default=0.2)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        candidate_paths=args.candidate_csv,
        candidate_globs=args.candidate_glob or None,
        pr_auc_min=args.pr_auc_min,
        topk_k=args.topk_k,
        topk_hit_rate_min=args.topk_hit_rate_min,
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_md(out_md, payload)


if __name__ == "__main__":
    main()
