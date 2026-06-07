#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_RUN_ROOT = (
    "runs/external_validation_blind_runs/"
    "external_validation_blind_runs_2026-04-30_gpcr_scaleup_100k_residualv4_apply_candidate_v1"
)
DEFAULT_OUT_JSON = "runs/gpcr_scaleup_100k_residualv4_apply_recovery_packet_current.json"
DEFAULT_OUT_MD = "runs/gpcr_scaleup_100k_residualv4_apply_recovery_packet_current.md"
DEFAULT_FAILURE_ANALYSIS_JSON = "runs/gpcr_100k_failure_analysis_current.json"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _is_truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        out = float(value)
        return out if out == out else None
    except Exception:
        return None


def _safe_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(float(value))
    except Exception:
        return None


def _normalize_path_string(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return str(_resolve(text))


def _optional_resolve(value: Any) -> Path | None:
    text = str(value or "").strip()
    if not text:
        return None
    return _resolve(text)


def _copied_summary_path(task: dict[str, Any]) -> Path:
    summary_src = str(task.get("summary_json", "") or "").strip()
    copied_files = task.get("copied_files", [])
    if isinstance(copied_files, list):
        for entry in copied_files:
            if not isinstance(entry, dict):
                continue
            if str(entry.get("src", "") or "").strip() != summary_src:
                continue
            dst = str(entry.get("dst", "") or "").strip()
            if dst:
                return _resolve(dst)
    return _resolve(summary_src)


def _derive_related_path(summary_json: Path, replacement: str) -> Path:
    name = summary_json.name
    if name.endswith("_summary.json"):
        return summary_json.with_name(name[: -len("_summary.json")] + replacement)
    return summary_json.with_name(summary_json.stem + replacement)


def _build_ranking_counts(ranking_rows_csv: Path, *, score_col: str) -> dict[str, Any]:
    row_count = 0
    positive_count = 0
    positive_ranks: list[int] = []
    top20_binder_count = 0
    top100_binder_count = 0
    top20_false_positives: list[dict[str, Any]] = []
    top20_false_positive_count = 0

    with ranking_rows_csv.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for rank, row in enumerate(reader, start=1):
            row_count += 1
            is_binder = _is_truthy(row.get("is_binder"))
            if is_binder:
                positive_count += 1
                positive_ranks.append(rank)
                if rank <= 20:
                    top20_binder_count += 1
                if rank <= 100:
                    top100_binder_count += 1
            else:
                if rank <= 20:
                    top20_false_positive_count += 1
                    if len(top20_false_positives) < 10:
                        top20_false_positives.append(
                            {
                                "ligand_id": str(row.get("ligand_id", "") or ""),
                                "mean_min_distance_A": _safe_float(row.get("mean_min_distance_A")),
                                "rank": rank,
                                "score": _safe_float(row.get(score_col)),
                            }
                        )

    return {
        "positive_count": positive_count,
        "positive_ranks": positive_ranks,
        "row_count": row_count,
        "top100_binder_count": top100_binder_count,
        "top20_binder_count": top20_binder_count,
        "top20_false_positive_count": top20_false_positive_count,
        "top20_false_positives": top20_false_positives,
    }


def _build_lane_payload(task: dict[str, Any]) -> dict[str, Any]:
    task_id = str(task.get("task_id", "") or "").strip()
    summary_json = _resolve(str(task.get("summary_json", "") or ""))
    pipeline_summary_json = _optional_resolve(task.get("pipeline_summary_json")) or summary_json
    task_summary = _load_json(pipeline_summary_json if pipeline_summary_json.exists() else summary_json)
    stage_summary_path = _derive_related_path(pipeline_summary_json, "_stage3_summary.json")
    stage_summary = _load_json(stage_summary_path)
    op_gate = task_summary.get("stages", {}).get("stage6_operational_gate", {})
    if not isinstance(op_gate, dict):
        op_gate = {}
    score_col = str(op_gate.get("ranking_score_col_used") or stage_summary.get("residual_prototype", {}).get("active_score_col") or "").strip()
    ranking_rows_csv = _derive_related_path(pipeline_summary_json, "_stage5_ranking_rows.csv")
    ranking_counts = _build_ranking_counts(ranking_rows_csv, score_col=score_col)
    service_result = task_summary.get("service_result", {})
    if not isinstance(service_result, dict):
        service_result = {}
    failed_stage = task_summary.get("failed_stage", service_result.get("failed_stage"))
    if not failed_stage:
        failed_stage = None
    return {
        "failed_metrics": list(op_gate.get("failed_metrics", []) if isinstance(op_gate.get("failed_metrics"), list) else []),
        "failed_stage": failed_stage,
        "lane": f"{task_id}_100k",
        "mean_min_distance_A": op_gate.get("mean_min_distance_A"),
        "min_frames_observed": _safe_int(op_gate.get("min_frames_observed")) or 0,
        "pass": bool(task_summary.get("pass", False)),
        "positive_count": _safe_int(op_gate.get("ranking_positive_count")) or ranking_counts["positive_count"],
        "ranking_bedroc": op_gate.get("ranking_bedroc"),
        "ranking_counts": ranking_counts,
        "ranking_ef1": op_gate.get("ranking_ef1"),
        "ranking_pr_auc": op_gate.get("ranking_pr_auc"),
        "ranking_pr_auc_ci_low": op_gate.get("ranking_pr_auc_ci_low"),
        "ranking_score_col_used": score_col,
        "ranking_unique_auc": op_gate.get("ranking_unique_auc"),
        "topk_hit_rate_at_20": op_gate.get("ranking_topk_hit_rate"),
    }


def _flatten_residual_effect(residual: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(residual, dict):
        residual = {}
    return {
        "gated_positive_delta_count": residual.get("gated_positive_delta_count"),
        "max_delta": residual.get("max_delta"),
        "mean_delta": residual.get("mean_delta"),
        "min_prior_pressure_for_delta": residual.get("min_prior_pressure_for_delta"),
        "min_raw_delta_for_activation": residual.get("min_raw_delta_for_activation"),
        "min_structural_weakness_for_delta": residual.get("min_structural_weakness_for_delta"),
        "positive_delta_count": residual.get("positive_delta_count"),
        "status": residual.get("status"),
        "yellow_band_count": residual.get("yellow_band_count"),
    }


def _render_bool(value: Any) -> str:
    return json.dumps(bool(value))


def _render_value(value: Any) -> str:
    if isinstance(value, bool):
        return _render_bool(value)
    if value is None:
        return "null"
    return str(value)


def _render_positive_ranks(positive_ranks: list[int]) -> str:
    if len(positive_ranks) <= 20:
        return json.dumps(positive_ranks)
    return f"first 20: {json.dumps(positive_ranks[:20])}"


def build_payload(
    *,
    source_run_root: str = DEFAULT_SOURCE_RUN_ROOT,
    generated_at_local: str | None = None,
) -> dict[str, Any]:
    source_root = _resolve(source_run_root)
    source_summary_path = source_root / "summary.json" if source_root.is_dir() else source_root
    source_summary = _load_json(source_summary_path)
    failure_analysis = _load_json(_resolve(DEFAULT_FAILURE_ANALYSIS_JSON))
    spec = _load_json(_resolve("runs/gpcr_scaleup_100k_apply_v4_candidate/specs/gpcr_scaleup_100k_residualv4_apply_candidate_v1.json"))

    sets = source_summary.get("sets", [])
    if not isinstance(sets, list):
        sets = []
    tasks_by_id: dict[str, dict[str, Any]] = {}
    copied_summary_paths: dict[str, Path] = {}
    pipeline_summary_paths: dict[str, Path] = {}
    for set_row in sets:
        if not isinstance(set_row, dict):
            continue
        tasks = set_row.get("tasks", [])
        if not isinstance(tasks, list):
            continue
        for task in tasks:
            if not isinstance(task, dict):
                continue
            task_id = str(task.get("task_id", "") or "").strip()
            if task_id:
                tasks_by_id[task_id] = task
                copied_summary_paths[task_id] = _copied_summary_path(task)
                pipeline_path = _optional_resolve(task.get("pipeline_summary_json"))
                if pipeline_path is not None:
                    pipeline_summary_paths[task_id] = pipeline_path

    core_task = tasks_by_id.get("gpcr_core_full", {})
    chembl50_task = tasks_by_id.get("gpcr_chembl50_full", {})
    if not core_task or not chembl50_task:
        raise KeyError("Expected gpcr_core_full and gpcr_chembl50_full tasks in the source run summary.")

    core_summary_json = copied_summary_paths["gpcr_core_full"]
    chembl50_summary_json = copied_summary_paths["gpcr_chembl50_full"]
    core_pipeline_summary_json = pipeline_summary_paths.get("gpcr_core_full")
    chembl50_pipeline_summary_json = pipeline_summary_paths.get("gpcr_chembl50_full")
    if core_pipeline_summary_json is None:
        core_pipeline_summary_json = _resolve(str(core_task.get("summary_json", "") or ""))
    if chembl50_pipeline_summary_json is None:
        chembl50_pipeline_summary_json = _resolve(str(chembl50_task.get("summary_json", "") or ""))
    core_stage3_summary_json = _derive_related_path(core_pipeline_summary_json, "_stage3_summary.json")
    chembl50_stage3_summary_json = _derive_related_path(chembl50_pipeline_summary_json, "_stage3_summary.json")
    core_ranking_rows_csv = _derive_related_path(core_pipeline_summary_json, "_stage5_ranking_rows.csv")
    chembl50_ranking_rows_csv = _derive_related_path(chembl50_pipeline_summary_json, "_stage5_ranking_rows.csv")
    core_lane = _build_lane_payload(core_task)
    chembl50_lane = _build_lane_payload(chembl50_task)
    core_stage3 = _load_json(core_stage3_summary_json)
    chembl50_stage3 = _load_json(chembl50_stage3_summary_json)
    residual_proto = core_stage3.get("residual_prototype", {})
    if not isinstance(residual_proto, dict):
        residual_proto = {}
    chembl50_residual_proto = chembl50_stage3.get("residual_prototype", {})
    if not isinstance(chembl50_residual_proto, dict):
        chembl50_residual_proto = {}
    source_residual_effect = (
        source_summary.get("residual_effect", {}) if isinstance(source_summary.get("residual_effect", {}), dict) else {}
    )
    core_residual_effect = source_residual_effect.get("core", residual_proto)
    if not isinstance(core_residual_effect, dict) or not core_residual_effect:
        core_residual_effect = residual_proto
    chembl50_residual_effect = source_residual_effect.get("chembl50", chembl50_residual_proto)
    if not isinstance(chembl50_residual_effect, dict) or not chembl50_residual_effect:
        chembl50_residual_effect = chembl50_residual_proto
    core_row_count = int(core_lane["ranking_counts"]["row_count"])
    core_top20_binder_count = int(core_lane["ranking_counts"]["top20_binder_count"])
    core_positive_count = int(core_lane["positive_count"])
    core_failed_metrics = list(core_lane["failed_metrics"])
    claim_safe = bool(core_lane["pass"] and chembl50_lane["pass"])
    router_promotion_allowed = bool(claim_safe and bool((spec.get("global_governance") or {}).get("router_promotion_allowed", False)))
    status = (
        "core_blocked_chembl50_passed"
        if (not core_lane["pass"] and chembl50_lane["pass"])
        else (
            "core_and_chembl50_passed"
            if (core_lane["pass"] and chembl50_lane["pass"])
            else (
                "core_passed_chembl50_blocked"
                if (core_lane["pass"] and not chembl50_lane["pass"])
                else "core_blocked_chembl50_blocked"
            )
        )
    )

    candidate = residual_proto
    if not isinstance(candidate, dict):
        candidate = {}

    if generated_at_local is None:
        generated_at_local = dt.datetime.now().astimezone().replace(microsecond=0).isoformat(timespec="seconds")

    payload = {
        "artifact_type": "gpcr_scaleup_100k_residualv4_apply_recovery_packet",
        "candidate": {
            "residual_family": str(candidate.get("family", "") or ""),
            "residual_mode": str(candidate.get("mode", "") or ""),
            "residual_spec_json": _normalize_path_string(candidate.get("spec_json", "")),
            "residual_tuning_variant": str(candidate.get("tuning_variant", "") or ""),
            "score_col": str(candidate.get("active_score_col", "") or ""),
            "tag": str(source_summary.get("tag", "") or ""),
        },
        "evidence_artifacts": {
            "chembl50_ranking_rows_csv": str(chembl50_ranking_rows_csv),
            "chembl50_stage3_summary_json": str(chembl50_stage3_summary_json),
            "chembl50_summary_json": str(chembl50_summary_json),
            "core_ranking_rows_csv": str(core_ranking_rows_csv),
            "core_stage3_summary_json": str(core_stage3_summary_json),
            "core_summary_json": str(core_summary_json),
            "failure_analysis_json": str(_resolve(DEFAULT_FAILURE_ANALYSIS_JSON)),
        },
        "generated_at_local": generated_at_local,
        "lanes": {
            "chembl50": chembl50_lane,
            "core": core_lane,
        },
        "next_required_work": [
            "Do not promote chembl50_v4 residual apply as a core GPCR scale-up repair.",
            "Design a new GPCR core hard-decoy scoring/residual candidate that directly penalizes prior-structure mismatch and weak contact support among top-ranked decoys.",
            "Acceptance for the next candidate: gpcr_core_full PR-AUC >= 0.55, PR-AUC CI low >= 0.45, top20 hit rate >= 0.20, while ChEMBL50 remains operational-gate pass.",
            "Only after core and expanded-OOD both pass should the scale-up summary and commercialization queue be refreshed for 100k/1m claims.",
        ],
        "residual_effect": {
            "chembl50": _flatten_residual_effect(chembl50_residual_effect),
            "core": _flatten_residual_effect(core_residual_effect),
        },
        "root_cause_hypothesis": {
            "evidence": [
                f"core residual positive_delta_count={_safe_int(core_residual_effect.get('positive_delta_count')) or 0} across {core_row_count} scored rows",
                f"core top20 binders={core_top20_binder_count} / max possible {core_positive_count}",
                f"core failed metrics={repr(core_failed_metrics)}",
                str(failure_analysis.get("summary", {}).get("interpretation", "") or ""),
            ],
            "primary": "Residual-v4 apply is too sparse for gpcr_core_full hard-decoy intrusion.",
        },
        "source_run_root": str(source_root.resolve()),
        "summary": {
            "claim_safe": claim_safe,
            "commercial_scaleup_ready": claim_safe,
            "decision": "keep_gpcr_scaleup_blocked_for_core_claims" if not claim_safe else "promote_gpcr_scaleup_100k_claims",
            "plain_language": (
                "ChEMBL50 expanded-OOD lane passes, but gpcr_core_full still fails operational PR-AUC/top20 guardrails, so 100k/1m commercial scale-up claims must remain blocked."
                if not claim_safe
                else "Both GPCR lanes pass, but router promotion remains governed by the frozen packet policy."
            ),
            "router_promotion_allowed": router_promotion_allowed,
            "status": status,
        },
    }
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    core = payload["lanes"]["core"]
    chembl50 = payload["lanes"]["chembl50"]
    core_counts = core["ranking_counts"]
    chembl50_counts = chembl50["ranking_counts"]
    core_failed_metrics = core["failed_metrics"]
    core_lane = core["lane"]
    core_positive_ranks = _render_positive_ranks(list(core_counts.get("positive_ranks", [])))
    chembl50_positive_ranks = _render_positive_ranks(list(chembl50_counts.get("positive_ranks", [])))
    thresholds = core_failed_metrics
    pr_auc_threshold = _render_value(thresholds[0].get("threshold") if len(thresholds) > 0 and isinstance(thresholds[0], dict) else 0.55)
    pr_auc_ci_low_threshold = _render_value(thresholds[1].get("threshold") if len(thresholds) > 1 and isinstance(thresholds[1], dict) else 0.45)
    top20_threshold = _render_value(thresholds[2].get("threshold") if len(thresholds) > 2 and isinstance(thresholds[2], dict) else 0.2)
    lines = [
        "# GPCR 100k residual-v4 apply recovery packet",
        "",
        f"- Generated: `{payload['generated_at_local']}`",
        f"- Candidate: `{payload['candidate']['tag']}`",
        f"- Decision: `{payload['summary']['decision']}`",
        f"- Claim safe: `{_render_bool(payload['summary']['claim_safe'])}`",
        "",
        "## Lane Results",
        "",
        "| Lane | Pass | PR-AUC | PR-AUC CI low | Top20 hit rate | AUC | EF1 | Positive ranks |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
        (
            f"| {core_lane} | {_render_bool(core['pass'])} | {core['ranking_pr_auc']:.6f} | "
            f"{core['ranking_pr_auc_ci_low']:.6f} | {core['topk_hit_rate_at_20']:.3f} | "
            f"{core['ranking_unique_auc']:.6f} | {core['ranking_ef1']:.3f} | {core_positive_ranks} |"
        ),
        (
            f"| {chembl50['lane']} | {_render_bool(chembl50['pass'])} | {chembl50['ranking_pr_auc']:.6f} | "
            f"{chembl50['ranking_pr_auc_ci_low']:.6f} | {chembl50['topk_hit_rate_at_20']:.3f} | "
            f"{chembl50['ranking_unique_auc']:.6f} | {chembl50['ranking_ef1']:.3f} | {chembl50_positive_ranks} |"
        ),
        "",
        "## Core Blocker",
        "",
        (
            f"`{core_lane}` remains blocked at `stage6_operational_gate`: "
            f"ranking_pr_auc={core['ranking_pr_auc']} < {pr_auc_threshold}, "
            f"ranking_pr_auc_ci_low={core['ranking_pr_auc_ci_low']} < {pr_auc_ci_low_threshold}, "
            f"topk_hit_rate@20={core['topk_hit_rate_at_20']} < {top20_threshold}."
        ),
        "",
        (
            f"The residual-v4 apply hook was active, but too sparse for this failure mode: "
            f"`positive_delta_count={payload['residual_effect']['core']['positive_delta_count']}`, "
            f"`mean_delta={payload['residual_effect']['core']['mean_delta']}`, "
            f"`max_delta={payload['residual_effect']['core']['max_delta']}` across "
            f"`{core_counts['row_count']}` scored rows."
        ),
        "",
        "## Decision",
        "",
        "Keep GPCR commercial scale-up claims blocked for 100k/1m. "
        "ChEMBL50 can be retained as bounded expanded-OOD evidence, but it cannot clear the core GPCR scale-up regression by itself.",
        "",
        "## Next Required Work",
        "",
        f"1. Build a new GPCR core hard-decoy residual/score candidate, not another blind threshold relaxation of chembl50-v4.",
        "2. Target prior-structure mismatch and weak contact support in top-ranked decoys directly.",
        (
            "3. Promote only if core PR-AUC >= 0.55, PR-AUC CI low >= 0.45, "
            "top20 hit rate >= 0.20, and ChEMBL50 remains pass."
        ),
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the GPCR 100k residual-v4 apply recovery packet.")
    parser.add_argument("--source-run-root", default=DEFAULT_SOURCE_RUN_ROOT)
    parser.add_argument("--generated-at-local", default="")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        source_run_root=str(args.source_run_root),
        generated_at_local=str(args.generated_at_local).strip() or None,
    )
    out_json = _resolve(str(args.out_json))
    out_md = _resolve(str(args.out_md))
    _write_json(out_json, payload)
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
