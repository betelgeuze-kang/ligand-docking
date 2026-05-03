#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import glob
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BENCHMARK_SUMMARY_JSON = "runs/ligand_scaleup_benchmark_summary_current.json"
DEFAULT_TRIAGE_JSON = "runs/gpcr_scaleup_regression_triage_current.json"
DEFAULT_ARTIFACT_GLOB = "runs/external_validation_*gpcr_core_full*p0_n100000*r1_stage5_ranking_summary.json"
DEFAULT_OUT_JSON = "runs/gpcr_core_rank_diagnostics_current.json"
DEFAULT_OUT_MD = "runs/gpcr_core_rank_diagnostics_current.md"


def _resolve(path_str: str) -> Path:
    path = Path(path_str)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _safe_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _is_positive(row: dict[str, Any]) -> bool:
    return _text(row.get("is_binder")).lower() in {"1", "true", "yes", "y"}


def _positive_ligand_ranks(rows: list[dict[str, str]], *, top_k: int | None = None) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for rank, row in enumerate(rows, start=1):
        if top_k is not None and rank > top_k:
            break
        if _is_positive(row):
            hits.append({"rank": rank, "ligand_id": _text(row.get("ligand_id"))})
    return hits


def _compact_rank_row(row: dict[str, str], rank: int, score_col: str) -> dict[str, Any]:
    return {
        "rank": rank,
        "target": _text(row.get("target")),
        "ligand_id": _text(row.get("ligand_id")),
        "is_binder": _is_positive(row),
        "role": _text(row.get("role")),
        "score": _safe_float(row.get(score_col)) if score_col else None,
        "mean_min_distance_A": _safe_float(row.get("mean_min_distance_A")),
    }


def _topk_composition(rows: list[dict[str, str]], *, score_col: str, top_k: int = 20) -> dict[str, Any]:
    top_rows = rows[:top_k]
    binder_count = sum(1 for row in top_rows if _is_positive(row))
    role_counts: dict[str, int] = {}
    target_counts: dict[str, int] = {}
    for row in top_rows:
        role = _text(row.get("role")) or "unknown"
        target = _text(row.get("target")) or "unknown"
        role_counts[role] = role_counts.get(role, 0) + 1
        target_counts[target] = target_counts.get(target, 0) + 1
    return {
        "k": int(top_k),
        "observed_rows": int(len(top_rows)),
        "binder_count": int(binder_count),
        "decoy_count": int(len(top_rows) - binder_count),
        "binder_fraction": float(binder_count / top_k) if top_k else None,
        "decoy_fraction": float((len(top_rows) - binder_count) / top_k) if top_k else None,
        "role_counts": dict(sorted(role_counts.items())),
        "target_counts": dict(sorted(target_counts.items())),
        "rows": [_compact_rank_row(row, rank, score_col) for rank, row in enumerate(top_rows, start=1)],
    }


def _average_precision_from_rows(rows: list[dict[str, str]]) -> float | None:
    positive_ranks = [hit["rank"] for hit in _positive_ligand_ranks(rows)]
    if not positive_ranks:
        return None
    return float(sum((idx + 1) / rank for idx, rank in enumerate(positive_ranks)) / len(positive_ranks))


def _top20_hit_rate(topk_rows: list[dict[str, str]], ranking_rows: list[dict[str, str]]) -> float | None:
    for row in topk_rows:
        if _text(row.get("k")) == "20":
            direct = _safe_float(row.get("hit_rate"))
            if direct is not None:
                return direct
            hits = _safe_float(row.get("hits"))
            if hits is not None:
                return float(hits / 20.0)
    if ranking_rows:
        return float(len(_positive_ligand_ranks(ranking_rows, top_k=20)) / 20.0)
    return None


def _stage5_base(summary_path: Path) -> str:
    suffix = "_stage5_ranking_summary.json"
    name = summary_path.name
    return name[: -len(suffix)] if name.endswith(suffix) else summary_path.stem


def _candidate_artifact_paths(summary_path: Path) -> dict[str, Path]:
    base = _stage5_base(summary_path)
    run_summary = summary_path.with_name(f"{base}_summary.json")
    top_level_base = re.sub(r"_p\d+_n\d+_r\d+$", "", base)
    return {
        "ranking_rows_csv": summary_path.with_name(f"{base}_stage5_ranking_rows.csv"),
        "ranking_topk_csv": summary_path.with_name(f"{base}_stage5_ranking_topk.csv"),
        "stage3_summary_json": summary_path.with_name(f"{base}_stage3_summary.json"),
        "stage3_scores_csv": summary_path.with_name(f"{base}_stage3_scores.csv"),
        "run_summary_json": run_summary,
        "top_level_summary_json": summary_path.with_name(f"{top_level_base}_summary.json"),
    }


def _score_column(summary: dict[str, Any], rows: list[dict[str, str]]) -> str:
    for key in ("score_col", "score_column", "probability_score_col", "probability_score_col_used"):
        value = _text(summary.get(key))
        if value:
            return value
    metrics = summary.get("metrics") if isinstance(summary.get("metrics"), dict) else {}
    for key in ("probability_score_col_used", "score_col", "score_column"):
        value = _text(metrics.get(key))
        if value:
            return value
    for row in rows:
        for key in row:
            if key.startswith("binding_score_"):
                return key
    return ""


def _metrics(summary: dict[str, Any], topk_rows: list[dict[str, str]], ranking_rows: list[dict[str, str]]) -> dict[str, Any]:
    summary_metrics = summary.get("metrics") if isinstance(summary.get("metrics"), dict) else {}
    pr_auc = _safe_float(summary_metrics.get("pr_auc", summary.get("pr_auc")))
    return {
        "pr_auc": pr_auc if pr_auc is not None else _average_precision_from_rows(ranking_rows),
        "top20_hit_rate": _top20_hit_rate(topk_rows, ranking_rows),
    }


def _infer_candidate_id(path: Path) -> str:
    source = path.name.lower()
    if "structure_support" in source or "structure-support" in source:
        return "gpcr_core_structure_support_rescore_v" + _version_after(source, "structure_support")
    if "fixed_reference" in source and "decoy_intrusion" in source:
        return "gpcr_core_fixed_reference_decoy_intrusion_v" + _version_after(source, "decoy_intrusion")
    if "decoy_intrusion" in source:
        return "gpcr_core_decoy_intrusion_v" + _version_after(source, "decoy_intrusion")
    if "mismatch_contact" in source:
        return "gpcr_core_mismatch_contact_v" + _version_after(source, "mismatch_contact")
    if "residualv4" in source:
        return "gpcr_core_residualv4_v" + _version_after(source, "residualv4")
    if "repair" in source:
        return "gpcr_core_repair_v" + _version_after(source, "repair")
    compact = re.sub(r"[^a-z0-9]+", "_", _stage5_base(path).lower()).strip("_")
    return compact or "gpcr_core_candidate"


def _version_after(source: str, token: str) -> str:
    match = re.search(rf"{re.escape(token)}.*?(?:_v|v)(\d+)", source)
    return match.group(1) if match else "1"


def _candidate_mode(path: Path) -> str:
    source = path.name.lower()
    if "shadow" in source:
        return "shadow"
    if "fixed_reference" in source:
        return "fixed_reference_apply"
    if "apply" in source or "guarded" in source:
        return "guarded_apply"
    return "comparison"


def _triage_candidates(triage: dict[str, Any]) -> list[dict[str, Any]]:
    rows = triage.get("candidates")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _matching_triage_row(
    path: Path,
    inferred_id: str,
    triage_rows: list[dict[str, Any]],
    extra_texts: list[str] | None = None,
) -> dict[str, Any]:
    if len(triage_rows) == 1:
        return triage_rows[0]
    path_text = " ".join([str(path), *(extra_texts or [])])
    for row in triage_rows:
        if _text(row.get("candidate_id")) == inferred_id:
            return row
    for row in sorted(triage_rows, key=lambda item: len(_text(item.get("artifact"))), reverse=True):
        if _text(row.get("artifact")) and _text(row.get("artifact")) in path_text:
            return row
    for row in sorted(triage_rows, key=lambda item: len(_text(item.get("tag"))), reverse=True):
        if _text(row.get("tag")) and _text(row.get("tag")) in path_text:
            return row
    return {}


def _stage3_scaling(stage3_summary: dict[str, Any], stage3_rows: list[dict[str, str]]) -> dict[str, Any]:
    scaling = stage3_summary.get("score_reference_scaling")
    if not isinstance(scaling, dict):
        scaling = {}
    row_modes = sorted({_text(row.get("score_scaling_mode")) for row in stage3_rows if _text(row.get("score_scaling_mode"))})
    row_hashes = sorted(
        {_text(row.get("score_reference_stats_hash")) for row in stage3_rows if _text(row.get("score_reference_stats_hash"))}
    )
    return {
        "mode": _text(scaling.get("mode")) or (row_modes[0] if len(row_modes) == 1 else ""),
        "status": _text(scaling.get("status")),
        "stats_json": _text(scaling.get("stats_json")),
        "stats_hash": _text(scaling.get("stats_hash")) or (row_hashes[0] if len(row_hashes) == 1 else ""),
        "applied_columns": list(scaling.get("applied_columns")) if isinstance(scaling.get("applied_columns"), list) else [],
        "missing_columns": list(scaling.get("missing_columns")) if isinstance(scaling.get("missing_columns"), list) else [],
        "fallback_columns": list(scaling.get("fallback_columns")) if isinstance(scaling.get("fallback_columns"), list) else [],
        "invalid_columns": list(scaling.get("invalid_columns")) if isinstance(scaling.get("invalid_columns"), list) else [],
        "row_score_scaling_modes": row_modes,
        "row_score_reference_stats_hashes": row_hashes,
    }


def _run_summary_snapshot(run_summary: dict[str, Any], top_level_summary: dict[str, Any]) -> dict[str, Any]:
    source = run_summary if run_summary else top_level_summary
    runs = top_level_summary.get("runs") if isinstance(top_level_summary.get("runs"), list) else []
    first_run = next((row for row in runs if isinstance(row, dict)), {})
    return {
        "pass": _safe_bool(source.get("pass")),
        "failed_stage": _text(source.get("failed_stage")) or _text(first_run.get("failed_stage")),
        "planned_runs": _safe_float(top_level_summary.get("planned_runs")),
        "completed_runs": _safe_float(top_level_summary.get("completed_runs")),
        "ranking_pr_auc": _safe_float(first_run.get("ranking_pr_auc")),
        "topk_hit_rate": _safe_float(first_run.get("topk_hit_rate")),
        "ranking_positive_count": _safe_float(first_run.get("ranking_positive_count")),
    }


def _reject_reason(run_summary: dict[str, Any], top_level_summary: dict[str, Any], triage_row: dict[str, Any]) -> dict[str, Any]:
    if _text(triage_row.get("reject_reason")):
        return {"source": "triage", "reason": _text(triage_row.get("reject_reason")), "failed_metrics": []}
    if _text(triage_row.get("reason")):
        return {"source": "triage", "reason": _text(triage_row.get("reason")), "failed_metrics": []}

    summaries = [run_summary, top_level_summary]
    for summary in summaries:
        stages = summary.get("stages") if isinstance(summary.get("stages"), dict) else {}
        gate = stages.get("stage6_operational_gate") if isinstance(stages.get("stage6_operational_gate"), dict) else {}
        failed_metrics = gate.get("failed_metrics") if isinstance(gate.get("failed_metrics"), list) else []
        if failed_metrics:
            return {
                "source": "stage6_operational_gate",
                "reason": "operational_gate_failed",
                "failed_stage": _text(summary.get("failed_stage")) or "stage6_operational_gate",
                "failed_metrics": failed_metrics,
            }
    failed_stage = _text(run_summary.get("failed_stage")) or _text(top_level_summary.get("failed_stage"))
    if failed_stage:
        return {"source": "run_summary", "reason": failed_stage, "failed_stage": failed_stage, "failed_metrics": []}
    return {"source": "", "reason": "", "failed_metrics": []}


def _candidate_row(summary_path: Path, triage_rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary = _read_json(summary_path)
    paths = _candidate_artifact_paths(summary_path)
    ranking_rows = _read_csv(paths["ranking_rows_csv"])
    topk_rows = _read_csv(paths["ranking_topk_csv"])
    stage3_summary = _read_json(paths["stage3_summary_json"])
    stage3_rows = _read_csv(paths["stage3_scores_csv"])
    run_summary = _read_json(paths["run_summary_json"])
    top_level_summary = _read_json(paths["top_level_summary_json"])
    inferred_id = _infer_candidate_id(summary_path)
    triage_row = _matching_triage_row(
        summary_path,
        inferred_id,
        triage_rows,
        extra_texts=[
            _text(top_level_summary.get("profile_json")),
            _text(run_summary.get("profile_json")),
            str(paths["top_level_summary_json"]),
            str(paths["run_summary_json"]),
        ],
    )
    candidate_id = _text(triage_row.get("candidate_id")) or inferred_id
    positive_ranks = _positive_ligand_ranks(ranking_rows)
    score_col = _score_column(summary, ranking_rows)
    run_snapshot = _run_summary_snapshot(run_summary, top_level_summary)
    reject_reason = _reject_reason(run_summary, top_level_summary, triage_row)
    pass_value = _safe_bool(run_snapshot.get("pass"))
    if pass_value is None:
        pass_value = _safe_bool(triage_row.get("pass"))
    if pass_value is None:
        pass_value = _safe_bool(summary.get("pass"))
    reject_evidence = triage_row.get("reject_evidence")
    if not isinstance(reject_evidence, bool):
        reject_evidence = pass_value is False or bool(_text(reject_reason.get("reason")))
    return {
        "candidate_id": candidate_id,
        "mode": _text(triage_row.get("mode")) or _candidate_mode(summary_path),
        "pass": pass_value,
        "claim_allowed": False,
        "comparison_only": True,
        "reject_evidence": bool(reject_evidence),
        "status": "reject_evidence" if reject_evidence else "comparison_only",
        "reject_reason": reject_reason,
        "score_column": score_col,
        "score_source": "stage5_ranking_summary",
        "run_summary": run_snapshot,
        "stage3": {
            "score_rows": int(len(stage3_rows)),
            "active_score_col": _text(stage3_summary.get("active_score_col")),
            "ranking_score_col_used": _text(stage3_summary.get("ranking_score_col_used")),
            "fixed_scaling": _stage3_scaling(stage3_summary, stage3_rows),
        },
        "positive_count": int(len(positive_ranks)),
        "positive_ligand_ranks": positive_ranks,
        "top20_positive_hits": _positive_ligand_ranks(ranking_rows, top_k=20),
        "top20_composition": _topk_composition(ranking_rows, score_col=score_col, top_k=20),
        "metrics": _metrics(summary, topk_rows, ranking_rows),
        "source_artifacts": {
            "stage5_ranking_summary_json": str(summary_path),
            "ranking_rows_csv": str(paths["ranking_rows_csv"]) if paths["ranking_rows_csv"].exists() else "",
            "ranking_topk_csv": str(paths["ranking_topk_csv"]) if paths["ranking_topk_csv"].exists() else "",
            "stage3_summary_json": str(paths["stage3_summary_json"]) if paths["stage3_summary_json"].exists() else "",
            "stage3_scores_csv": str(paths["stage3_scores_csv"]) if paths["stage3_scores_csv"].exists() else "",
            "run_summary_json": str(paths["run_summary_json"]) if paths["run_summary_json"].exists() else "",
            "top_level_summary_json": str(paths["top_level_summary_json"]) if paths["top_level_summary_json"].exists() else "",
        },
    }


def _primary_blocker(benchmark: dict[str, Any], triage: dict[str, Any]) -> str:
    regression = benchmark.get("regression_diagnostics")
    if isinstance(regression, dict) and _text(regression.get("primary_regression_task_id")):
        return _text(regression.get("primary_regression_task_id"))
    summary = triage.get("summary")
    if isinstance(summary, dict) and _text(summary.get("primary_blocker_task")):
        return _text(summary.get("primary_blocker_task"))
    return "gpcr_core_full"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    benchmark = _read_json(_resolve(args.benchmark_summary_json))
    triage = _read_json(_resolve(args.triage_json))
    triage_rows = _triage_candidates(triage)
    summary_paths = sorted(Path(path) for path in glob.glob(str(_resolve(args.artifact_glob))))
    candidates = [_candidate_row(path, triage_rows) for path in summary_paths]
    candidates.sort(key=lambda row: str(row.get("candidate_id", "")))
    rejected_count = sum(1 for row in candidates if row.get("reject_evidence") is True)
    return {
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "summary": {
            "claim_safe": False,
            "claim_safe_status": "diagnostic_only_not_claim_safe",
            "input_claim_safe_values": {
                "benchmark_summary": _safe_bool(benchmark.get("claim_safe")),
                "triage_summary": _safe_bool((triage.get("summary") or {}).get("claim_safe"))
                if isinstance(triage.get("summary"), dict)
                else None,
            },
            "primary_blocker_task": _primary_blocker(benchmark, triage),
            "candidate_count": int(len(candidates)),
            "rejected_candidate_count": int(rejected_count),
            "comparison_only_candidate_count": int(len(candidates)),
        },
        "candidates": candidates,
        "input_artifacts": {
            "benchmark_summary_json": str(_resolve(args.benchmark_summary_json)),
            "triage_json": str(_resolve(args.triage_json)),
            "artifact_glob": args.artifact_glob,
        },
    }


def _write_md(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# GPCR Core Rank Diagnostics",
        "",
        "## Summary",
        "",
        f"- claim_safe: `{summary['claim_safe']}`",
        f"- claim_safe_status: `{summary['claim_safe_status']}`",
        f"- primary_blocker_task: `{summary['primary_blocker_task']}`",
        f"- candidate_count: `{summary['candidate_count']}`",
        f"- rejected_candidate_count: `{summary['rejected_candidate_count']}`",
        "",
        "## Candidates",
        "",
        "| candidate_id | status | reject_reason | score_column | scaling | pr_auc | top20 binders/decoys | positive_ranks |",
        "| --- | --- | --- | --- | --- | ---: | ---: | --- |",
    ]
    for row in payload.get("candidates", []):
        metrics = row.get("metrics") if isinstance(row.get("metrics"), dict) else {}
        ranks = [hit.get("rank") for hit in row.get("positive_ligand_ranks", []) if isinstance(hit, dict)]
        top20 = row.get("top20_composition") if isinstance(row.get("top20_composition"), dict) else {}
        stage3 = row.get("stage3") if isinstance(row.get("stage3"), dict) else {}
        scaling = stage3.get("fixed_scaling") if isinstance(stage3.get("fixed_scaling"), dict) else {}
        reject = row.get("reject_reason") if isinstance(row.get("reject_reason"), dict) else {}
        scaling_label = _text(scaling.get("mode"))
        if _text(scaling.get("stats_hash")):
            scaling_label = f"{scaling_label}:{_text(scaling.get('stats_hash'))[:12]}"
        lines.append(
            f"| `{row.get('candidate_id', '')}` | `{row.get('status', '')}` | `{reject.get('reason', '')}` | "
            f"`{row.get('score_column', '')}` | `{scaling_label}` | {metrics.get('pr_auc')} | "
            f"{top20.get('binder_count')}/{top20.get('decoy_count')} | `{ranks}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_outputs(args: argparse.Namespace) -> dict[str, Any]:
    payload = build_payload(args)
    out_json = _resolve(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    _write_md(_resolve(args.out_md), payload)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build diagnostic-only GPCR core rank artifacts without changing claim thresholds."
    )
    parser.add_argument("--benchmark-summary-json", default=DEFAULT_BENCHMARK_SUMMARY_JSON)
    parser.add_argument("--triage-json", default=DEFAULT_TRIAGE_JSON)
    parser.add_argument("--artifact-glob", default=DEFAULT_ARTIFACT_GLOB)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    write_outputs(parse_args())


if __name__ == "__main__":
    main()
