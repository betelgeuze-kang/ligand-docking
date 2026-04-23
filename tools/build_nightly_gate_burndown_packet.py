#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"

DEFAULT_OUT_JSON = "runs/nightly_gate_burndown_packet_current.json"
DEFAULT_OUT_CSV = "runs/nightly_gate_burndown_packet_current.csv"
DEFAULT_OUT_MD = "runs/nightly_gate_burndown_packet_current.md"

_TOP_NIGHTLY_RE = re.compile(r"ligand_htvs_nightly_(\d{4}-\d{2}-\d{2})_summary\.json$")


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _fmt_float(value: Any, digits: int = 3) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "-"


def _round_up(value: float, step: float = 0.05) -> float:
    if value <= 0:
        return 0.0
    return round(math.ceil(value / step) * step, 3)


def _load_json(path_like: str | Path) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _maybe_load_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _maybe_load_csv_rows(path_like: str | Path) -> list[dict[str, Any]]:
    if not _text(path_like):
        return []
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row or {}) for row in csv.DictReader(fh)]


def _discover_latest_top_nightly() -> Path | None:
    candidates: list[tuple[str, Path]] = []
    for path in RUNS.glob("ligand_htvs_nightly_*_summary.json"):
        match = _TOP_NIGHTLY_RE.fullmatch(path.name)
        if match:
            candidates.append((match.group(1), path))
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: item[0])[-1][1]


def _recent_top_nightly_paths(limit: int = 3) -> list[Path]:
    candidates: list[tuple[str, Path]] = []
    for path in RUNS.glob("ligand_htvs_nightly_*_summary.json"):
        match = _TOP_NIGHTLY_RE.fullmatch(path.name)
        if match:
            candidates.append((match.group(1), path))
    return [path for _, path in sorted(candidates, key=lambda item: item[0])[-limit:]]


def _primary_failed_stage(payload: dict[str, Any]) -> str:
    top = _text(payload.get("failed_stage"))
    if top and top != "smoke":
        return top
    smoke = dict(payload.get("stages", {}) or {}).get("smoke")
    if isinstance(smoke, dict):
        smoke_stage = _text(smoke.get("failed_stage"))
        if smoke_stage:
            return smoke_stage
    return top


def _top_error_code(payload: dict[str, Any]) -> str:
    return _text(dict(payload.get("service_result", {}) or {}).get("error_code"))


def _derive_companion_artifact(latest_nightly_artifact: str, suffix: str) -> str:
    if not latest_nightly_artifact.endswith("_summary.json"):
        return ""
    return latest_nightly_artifact.replace("_summary.json", suffix)


def _derive_smoke_companion_artifact(latest_nightly_artifact: str, suffix: str) -> str:
    if not latest_nightly_artifact.endswith("_summary.json"):
        return ""
    return latest_nightly_artifact.replace("_summary.json", f"_smoke{suffix}")


def _companion_candidates(latest_nightly_artifact: str, suffix: str) -> list[str]:
    candidates = [
        _derive_companion_artifact(latest_nightly_artifact, suffix),
        _derive_smoke_companion_artifact(latest_nightly_artifact, suffix),
    ]
    seen: set[str] = set()
    out: list[str] = []
    for candidate in candidates:
        candidate_text = _text(candidate)
        if candidate_text and candidate_text not in seen:
            seen.add(candidate_text)
            out.append(candidate_text)
    return out


def _resolve_existing_companion_artifact(latest_nightly_artifact: str, suffix: str) -> str:
    candidates = _companion_candidates(latest_nightly_artifact, suffix)
    for candidate in candidates:
        if _resolve(candidate).exists():
            return candidate
    return candidates[0] if candidates else ""


def _extract_stage(payload: dict[str, Any], stage_name: str) -> dict[str, Any]:
    stages = dict(payload.get("stages", {}) or {})
    direct = stages.get(stage_name)
    if isinstance(direct, dict) and direct:
        return dict(direct)
    smoke = stages.get("smoke")
    if isinstance(smoke, dict):
        nested = dict(smoke.get("stages", {}) or {}).get(stage_name)
        if isinstance(nested, dict) and nested:
            return dict(nested)
    return {}


def _recent_transition_line(recent_payloads: list[dict[str, Any]], recent_artifacts: list[str]) -> str:
    parts: list[str] = []
    for artifact, payload in zip(recent_artifacts, recent_payloads):
        match = _TOP_NIGHTLY_RE.fullmatch(Path(artifact).name)
        date_tag = match.group(1) if match else Path(artifact).name
        parts.append(f"{date_tag}:{_primary_failed_stage(payload) or '-'}")
    return " -> ".join(parts)


def _recent_stage6_fail_count(recent_payloads: list[dict[str, Any]]) -> int:
    return sum(
        1
        for payload in recent_payloads
        if _primary_failed_stage(payload) == "stage6_operational_gate" or _top_error_code(payload) == "HTVS_GATE_FAILED"
    )


def _band_key(target: Any, ligand_id: Any) -> str:
    target_text = _text(target)
    ligand_text = _text(ligand_id)
    return f"{target_text}::{ligand_text}" if target_text or ligand_text else ""


def _band_sort_score(row: dict[str, Any], score_col: str, lower_better: bool) -> tuple[float, str, str]:
    score = _float(row.get(score_col))
    score_key = score if lower_better else -score
    return (score_key, _text(row.get("target")).lower(), _text(row.get("ligand_id")).lower())


def _stage5_artifacts(
    latest_nightly_artifact: str,
    stage5_payload: dict[str, Any],
    stage5_artifact: str,
) -> dict[str, str]:
    artifacts = dict(stage5_payload.get("artifacts", {}) or {})
    detail_csv = _text(artifacts.get("detail_csv")) or _resolve_existing_companion_artifact(
        latest_nightly_artifact, "_stage5_ranking_rows.csv"
    )
    topk_csv = _text(artifacts.get("topk_csv")) or _resolve_existing_companion_artifact(
        latest_nightly_artifact, "_stage5_ranking_topk.csv"
    )
    unique_csv = _text(artifacts.get("unique_csv")) or _resolve_existing_companion_artifact(
        latest_nightly_artifact, "_stage5_ranking_unique.csv"
    )
    summary_json = _text(artifacts.get("summary_json")) or stage5_artifact
    summary_md = _text(artifacts.get("summary_md")) or _resolve_existing_companion_artifact(
        latest_nightly_artifact, "_stage5_ranking_summary.md"
    )
    stage4_scores_csv = _resolve_existing_companion_artifact(
        latest_nightly_artifact, "_stage4_calibration_scores.csv"
    )
    stage4_summary_json = _resolve_existing_companion_artifact(
        latest_nightly_artifact, "_stage4_calibration_summary.json"
    )
    stage4_summary_md = _resolve_existing_companion_artifact(
        latest_nightly_artifact, "_stage4_calibration_summary.md"
    )
    return {
        "stage4_scores_csv": stage4_scores_csv,
        "stage4_summary_json": stage4_summary_json,
        "stage4_summary_md": stage4_summary_md,
        "stage5_summary_json": summary_json,
        "stage5_summary_md": summary_md,
        "stage5_detail_csv": detail_csv,
        "stage5_topk_csv": topk_csv,
        "stage5_unique_csv": unique_csv,
    }


def _build_stage4_replica_index(stage4_score_rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in stage4_score_rows:
        key = _band_key(row.get("target"), row.get("ligand_id"))
        if not key or _float(row.get("mean_min_distance_A")) <= 0:
            continue
        index[key].append(dict(row or {}))
    return index


def _build_threshold_candidate_rows(
    *,
    band_rows: list[dict[str, Any]],
    current_threshold: float,
    band_mean: float,
) -> list[dict[str, Any]]:
    if not band_rows:
        return []
    values = [_float(row.get("mean_min_distance_A")) for row in band_rows if _float(row.get("mean_min_distance_A")) > 0]
    if not values:
        return []
    sorted_values = sorted(values)
    candidate_specs = [
        ("current_gate", current_threshold, "current stage6 operational gate"),
        ("band_mean_exact", band_mean, "exact threshold needed to clear the current band mean"),
        ("band_mean_step_0.05", _round_up(band_mean, 0.05), "nearest 0.05A threshold that would clear the current band mean"),
        (
            f"member_cover_{max(1, math.ceil(len(sorted_values) * 0.75))}_of_{len(sorted_values)}",
            _round_up(sorted_values[max(0, math.ceil(len(sorted_values) * 0.75) - 1)], 0.05),
            "nearest 0.05A threshold that would cover roughly three quarters of the current band members",
        ),
        ("full_band_cover_step_0.05", _round_up(max(sorted_values), 0.05), "nearest 0.05A threshold that would clear every current band member"),
    ]
    rows: list[dict[str, Any]] = []
    seen_thresholds: set[float] = set()
    for label, threshold, notes in candidate_specs:
        if threshold <= 0 or threshold in seen_thresholds:
            continue
        seen_thresholds.add(threshold)
        member_pass_count = sum(1 for value in sorted_values if value <= threshold)
        worst_member_delta = max((value - threshold for value in sorted_values), default=0.0)
        rows.append(
            {
                "row_kind": "threshold_candidate",
                "candidate_label": label,
                "candidate_threshold_A": threshold,
                "band_mean_A": band_mean,
                "band_mean_delta_A": round(band_mean - threshold, 3),
                "band_mean_pass": bool(band_mean <= threshold + 1e-12),
                "member_pass_count": member_pass_count,
                "member_total_count": len(sorted_values),
                "member_pass_pct": round((member_pass_count / len(sorted_values)) * 100.0, 1),
                "worst_member_delta_A": round(worst_member_delta, 3),
                "notes": notes,
            }
        )
    return rows


def _execution_recommendation(
    *,
    culprit_band_rows: list[dict[str, Any]],
    primary_metric_name: str,
    primary_metric_delta: float,
    stage5_unique_artifact: str,
) -> str:
    if not culprit_band_rows:
        return (
            "Refresh the stage5 unique ranking artifact first so the stage6 culprit band can be reconstructed before retrying."
        )
    positive_rows = [
        row
        for row in culprit_band_rows
        if _float(row.get("delta_vs_gate_threshold_A")) > 0
    ]
    positive_rows.sort(key=lambda row: _float(row.get("mean_delta_contribution_A")), reverse=True)
    if not positive_rows:
        return (
            f"Keep `{primary_metric_name or 'mean_min_distance_A'}` stable and re-run the packet; the current culprit band has no "
            "positive contributors above the gate threshold."
        )

    focus_rows = positive_rows[:2]
    focus_labels = [f"{_text(row.get('target'))}/{_text(row.get('ligand_id'))}" for row in focus_rows]
    covered_delta = sum(_float(row.get("mean_delta_contribution_A")) for row in focus_rows)
    first = focus_rows[0]
    lead_label = focus_labels[0]
    lead_value = _float(first.get("mean_min_distance_A"))
    lead_delta = _float(first.get("delta_vs_gate_threshold_A"))
    if len(focus_rows) == 1:
        return (
            f"Start with `{lead_label}` from `{stage5_unique_artifact}`: its band distance is `{_fmt_float(lead_value)}`A "
            f"(`+{_fmt_float(lead_delta)}`A vs gate) and it alone carries `{_fmt_float(covered_delta)}`A of the "
            f"`{_fmt_float(primary_metric_delta)}`A net `{primary_metric_name or 'mean_min_distance_A'}` overage."
        )

    return (
        "Start with "
        f"`{focus_labels[0]}` and `{focus_labels[1]}` from `{stage5_unique_artifact}`: they carry "
        f"`{_fmt_float(covered_delta)}`A of the `{_fmt_float(primary_metric_delta)}`A net "
        f"`{primary_metric_name or 'mean_min_distance_A'}` overage, so they are the fastest band members to tune before "
        "widening the gate."
    )


def _build_culprit_band_context(
    *,
    latest_nightly_artifact: str,
    stage5_payload: dict[str, Any],
    stage5_artifact: str,
    stage6: dict[str, Any],
    primary_metric_name: str,
    primary_metric_value: float,
    primary_metric_threshold: float,
    stage4_score_rows: list[dict[str, Any]] | None,
    stage5_detail_rows: list[dict[str, Any]] | None,
    stage5_unique_rows: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    artifacts = _stage5_artifacts(latest_nightly_artifact, stage5_payload, stage5_artifact)
    if stage4_score_rows is None:
        stage4_score_rows = _maybe_load_csv_rows(artifacts["stage4_scores_csv"])
    if stage5_detail_rows is None:
        stage5_detail_rows = _maybe_load_csv_rows(artifacts["stage5_detail_csv"])
    if stage5_unique_rows is None:
        stage5_unique_rows = _maybe_load_csv_rows(artifacts["stage5_unique_csv"])

    stage4_index = _build_stage4_replica_index(stage4_score_rows)
    gate_source = _text(stage6.get("mean_min_distance_A_source"))
    lower_better = bool(stage5_payload.get("lower_better", True))
    score_col = _text(stage5_payload.get("score_col")) or _text(stage6.get("ranking_score_col_used"))
    probability_score_col = (
        _text(stage5_payload.get("probability_score_col"))
        or _text(stage6.get("ranking_probability_score_col_used"))
        or score_col
    )
    requested_topk_k = _int(stage6.get("mean_min_distance_A_topk_k")) or _int(stage5_payload.get("distance_topk_k"))
    band_source_rows: list[dict[str, Any]] = []
    band_source_label = gate_source

    if gate_source in {"eval_unique_topk", "eval_unique_mean"} and stage5_unique_rows:
        ordered_unique = sorted(
            [dict(row or {}) for row in stage5_unique_rows if _float((row or {}).get("mean_min_distance_A")) > 0],
            key=lambda row: _band_sort_score(row, score_col, lower_better),
        )
        if gate_source == "eval_unique_topk":
            selected_count = min(max(requested_topk_k, 1), len(ordered_unique))
            band_source_rows = ordered_unique[:selected_count]
            band_source_label = f"{gate_source}({selected_count})"
        else:
            band_source_rows = ordered_unique
            band_source_label = f"{gate_source}({len(ordered_unique)})"
    elif gate_source == "scores_all_mean" and stage4_score_rows:
        band_source_rows = [dict(row or {}) for row in stage4_score_rows if _float((row or {}).get("mean_min_distance_A")) > 0]
        band_source_rows.sort(key=lambda row: _band_sort_score(row, score_col or "binding_energy_mmpbsa_kcal_mol_proxy", lower_better))
        band_source_label = f"scores_all_mean({len(band_source_rows)})"

    culprit_band_rows: list[dict[str, Any]] = []
    for band_rank, row in enumerate(band_source_rows, start=1):
        key = _band_key(row.get("target"), row.get("ligand_id"))
        stage4_rows_for_key = stage4_index.get(key, [])
        stage4_distances = [_float(stage4_row.get("mean_min_distance_A")) for stage4_row in stage4_rows_for_key]
        stage4_distances = [value for value in stage4_distances if value > 0]
        worst_stage4_row = (
            max(stage4_rows_for_key, key=lambda item: _float(item.get("mean_min_distance_A")))
            if stage4_rows_for_key
            else {}
        )
        best_stage4_row = (
            min(stage4_rows_for_key, key=lambda item: _float(item.get("mean_min_distance_A")))
            if stage4_rows_for_key
            else {}
        )
        value = _float(row.get("mean_min_distance_A"))
        delta_vs_gate = value - primary_metric_threshold
        contribution = delta_vs_gate / max(len(band_source_rows), 1)
        culprit_band_rows.append(
            {
                "row_kind": "culprit_band_member",
                "band_rank": band_rank,
                "band_scope": band_source_label,
                "target": _text(row.get("target")),
                "ligand_id": _text(row.get("ligand_id")),
                "band_key": key,
                "is_binder": _int(row.get("is_binder")) if _text(row.get("is_binder")) else "",
                "reference_binding_kcal_mol": _text(row.get("reference_binding_kcal_mol")),
                "score_col": score_col,
                "score_value": _float(row.get(score_col)),
                "probability_score_col": probability_score_col,
                "probability_score_value": _float(row.get(probability_score_col)),
                "mean_min_distance_A": value,
                "delta_vs_gate_threshold_A": round(delta_vs_gate, 3),
                "mean_delta_contribution_A": round(contribution, 3),
                "replica_count": len(stage4_rows_for_key),
                "replica_mean_distance_A": round(sum(stage4_distances) / len(stage4_distances), 3) if stage4_distances else 0.0,
                "replica_min_distance_A": round(min(stage4_distances), 3) if stage4_distances else 0.0,
                "replica_max_distance_A": round(max(stage4_distances), 3) if stage4_distances else 0.0,
                "best_replica_queue_id": _text(best_stage4_row.get("queue_id")),
                "best_replica_distance_A": round(_float(best_stage4_row.get("mean_min_distance_A")), 3) if best_stage4_row else 0.0,
                "worst_replica_queue_id": _text(worst_stage4_row.get("queue_id")),
                "worst_replica_distance_A": round(_float(worst_stage4_row.get("mean_min_distance_A")), 3) if worst_stage4_row else 0.0,
                "source_artifact": artifacts["stage5_unique_csv"] if gate_source.startswith("eval_unique") else artifacts["stage4_scores_csv"],
            }
        )

    band_mean = (
        round(sum(_float(row.get("mean_min_distance_A")) for row in culprit_band_rows) / len(culprit_band_rows), 6)
        if culprit_band_rows
        else 0.0
    )
    worst_row = max(culprit_band_rows, key=lambda row: _float(row.get("delta_vs_gate_threshold_A")), default={})
    member_pass_count = sum(
        1
        for row in culprit_band_rows
        if _float(row.get("mean_min_distance_A")) <= primary_metric_threshold + 1e-12
    )
    threshold_candidate_rows = _build_threshold_candidate_rows(
        band_rows=culprit_band_rows,
        current_threshold=primary_metric_threshold,
        band_mean=band_mean or primary_metric_value,
    )

    return {
        "artifacts": artifacts,
        "culprit_band_rows": culprit_band_rows,
        "threshold_candidate_rows": threshold_candidate_rows,
        "summary": {
            "culprit_band_supported": bool(culprit_band_rows),
            "culprit_band_source_label": band_source_label,
            "culprit_band_source_artifact": artifacts["stage5_unique_csv"] if gate_source.startswith("eval_unique") else artifacts["stage4_scores_csv"],
            "culprit_band_row_count": len(culprit_band_rows),
            "culprit_band_member_pass_count_at_current_gate": member_pass_count,
            "culprit_band_member_total_count": len(culprit_band_rows),
            "culprit_band_member_pass_pct_at_current_gate": (
                round((member_pass_count / len(culprit_band_rows)) * 100.0, 1) if culprit_band_rows else 0.0
            ),
            "culprit_band_mean_distance_A": band_mean or primary_metric_value,
            "culprit_band_matches_primary_metric": bool(
                culprit_band_rows and abs((band_mean or 0.0) - primary_metric_value) <= 1e-6
            ),
            "culprit_band_worst_key": _text(worst_row.get("band_key")),
            "culprit_band_worst_distance_A": _float(worst_row.get("mean_min_distance_A")),
            "culprit_band_worst_delta_A": _float(worst_row.get("delta_vs_gate_threshold_A")),
            "threshold_candidate_count": len(threshold_candidate_rows),
        },
    }


def build_payload(
    latest_nightly_payload: dict[str, Any],
    latest_nightly_artifact: str,
    stage2_payload: dict[str, Any],
    stage2_artifact: str,
    stage5_payload: dict[str, Any],
    stage5_artifact: str,
    recent_nightly_payloads: list[dict[str, Any]],
    recent_nightly_artifacts: list[str],
    stage4_score_rows: list[dict[str, Any]] | None = None,
    stage5_detail_rows: list[dict[str, Any]] | None = None,
    stage5_unique_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    stage6 = _extract_stage(latest_nightly_payload, "stage6_operational_gate")
    stage2 = dict(stage2_payload or {}) or _extract_stage(latest_nightly_payload, "stage2_trajectory_generation")
    latest_pass = bool(latest_nightly_payload.get("pass", False))
    latest_failed_stage = _primary_failed_stage(latest_nightly_payload)
    latest_error_code = _top_error_code(latest_nightly_payload)
    gate_failed = latest_failed_stage == "stage6_operational_gate" or latest_error_code == "HTVS_GATE_FAILED"
    failed_metrics = list(stage6.get("failed_metrics") or [])
    primary_metric = dict(failed_metrics[0] or {}) if failed_metrics else {}
    primary_metric_name = _text(primary_metric.get("metric"))
    primary_metric_value = _float(primary_metric.get("value"))
    primary_metric_threshold = _float(primary_metric.get("threshold"))
    primary_metric_delta = primary_metric_value - primary_metric_threshold
    stage2_recovered = (
        bool(stage2)
        and not bool(stage2.get("aborted_early", False))
        and _int(stage2.get("failed_rows")) == 0
        and _int(stage2.get("ok_rows")) == _int(stage2.get("queue_rows"))
    )
    transition_line = _recent_transition_line(recent_nightly_payloads, recent_nightly_artifacts)
    recent_stage6_fail_count = _recent_stage6_fail_count(recent_nightly_payloads)

    rows: list[dict[str, Any]] = []
    for rank, metric in enumerate(failed_metrics, start=1):
        value = _float(metric.get("value"))
        threshold = _float(metric.get("threshold"))
        rows.append(
            {
                "row_kind": "gate_failure_metric",
                "gate_rank": rank,
                "metric": _text(metric.get("metric")),
                "value": value,
                "threshold": threshold,
                "delta_over_threshold": value - threshold,
                "source": _text(stage6.get("mean_min_distance_A_source")),
                "topk_k": _int(stage6.get("mean_min_distance_A_topk_k")),
                "stage2_recovered": stage2_recovered,
                "stage2_ok_rows": _int(stage2.get("ok_rows")),
                "stage2_queue_rows": _int(stage2.get("queue_rows")),
                "ranking_auc": _float(stage6.get("ranking_auc")),
                "ranking_pr_auc": _float(stage6.get("ranking_pr_auc")),
                "ranking_ef1": _float(stage6.get("ranking_ef1")),
                "ranking_topk_hit_rate": _float(stage6.get("ranking_topk_hit_rate")),
                "ranking_ece": _float(stage6.get("ranking_ece")),
            }
        )

    stage6_context = _build_culprit_band_context(
        latest_nightly_artifact=latest_nightly_artifact,
        stage5_payload=stage5_payload,
        stage5_artifact=stage5_artifact,
        stage6=stage6,
        primary_metric_name=primary_metric_name,
        primary_metric_value=primary_metric_value,
        primary_metric_threshold=primary_metric_threshold,
        stage4_score_rows=stage4_score_rows,
        stage5_detail_rows=stage5_detail_rows,
        stage5_unique_rows=stage5_unique_rows,
    )
    culprit_band_rows = list(stage6_context.get("culprit_band_rows", []) or [])
    threshold_candidate_rows = list(stage6_context.get("threshold_candidate_rows", []) or [])
    rows.extend(culprit_band_rows)
    rows.extend(threshold_candidate_rows)

    if latest_pass:
        status = "nightly_gate_green"
        status_line = "latest nightly stage6 gate is green; keep the recovered writer/import path stable."
        next_required_step = "Keep the nightly stage6 gate green and avoid reopening upstream writer/import regressions."
    elif gate_failed:
        status = "nightly_gate_burndown_ready"
        status_line = (
            "stage2 is recovered and the nightly lane is now burning down the stage6 gate at "
            f"{primary_metric_name or 'stage6_metric'}={_fmt_float(primary_metric_value)} versus "
            f"{_fmt_float(primary_metric_threshold)} (+{_fmt_float(primary_metric_delta)} over threshold)."
            if failed_metrics
            else "stage2 is recovered and the nightly lane is blocked at stage6, but no failed metric rows were captured."
        )
        next_required_step = (
            "Keep stage2 recovered and tune the stage6 operational gate via "
            f"`{DEFAULT_OUT_MD}`: move `{primary_metric_name or 'mean_min_distance_A'}` down by "
            f"`{_fmt_float(primary_metric_delta)}` from `{_fmt_float(primary_metric_value)}` to at most "
            f"`{_fmt_float(primary_metric_threshold)}` while recent stage6 fails stay at "
            f"`{recent_stage6_fail_count}/{max(len(recent_nightly_payloads), 1)}`."
            if failed_metrics
            else "Keep stage2 recovered and refresh the stage6 packet so the failed metric stack is explicitly captured before the next retry."
        )
    else:
        status = "waiting_for_stage6_reentry"
        status_line = (
            "nightly is not reaching the stage6 gate yet; upstream recovery is still required before gate burndown becomes actionable."
        )
        next_required_step = (
            "Recover upstream nightly failures first so the run reaches stage6 again; only then use this packet as the burndown surface."
        )

    artifacts = dict(stage6_context.get("artifacts", {}) or {})
    culprit_summary = dict(stage6_context.get("summary", {}) or {})
    execution_recommendation = _execution_recommendation(
        culprit_band_rows=culprit_band_rows,
        primary_metric_name=primary_metric_name,
        primary_metric_delta=primary_metric_delta,
        stage5_unique_artifact=_text(culprit_summary.get("culprit_band_source_artifact")) or artifacts.get("stage5_unique_csv", ""),
    )
    source_artifacts = [
        latest_nightly_artifact,
        stage2_artifact,
        artifacts.get("stage4_scores_csv", ""),
        artifacts.get("stage4_summary_json", ""),
        stage5_artifact,
        artifacts.get("stage5_summary_md", ""),
        artifacts.get("stage5_detail_csv", ""),
        artifacts.get("stage5_topk_csv", ""),
        artifacts.get("stage5_unique_csv", ""),
    ]
    source_artifacts = [artifact for artifact in source_artifacts if _text(artifact)]
    source_artifacts = list(dict.fromkeys(source_artifacts))

    summary = {
        "packet_ready": bool(latest_nightly_payload),
        "packet_artifact": DEFAULT_OUT_MD,
        "nightly_summary_artifact": latest_nightly_artifact,
        "stage2_summary_artifact": stage2_artifact,
        "stage4_scores_artifact": _text(artifacts.get("stage4_scores_csv")),
        "stage4_summary_artifact": _text(artifacts.get("stage4_summary_json")),
        "stage5_summary_artifact": stage5_artifact,
        "stage5_detail_artifact": _text(artifacts.get("stage5_detail_csv")),
        "stage5_topk_artifact": _text(artifacts.get("stage5_topk_csv")),
        "stage5_unique_artifact": _text(artifacts.get("stage5_unique_csv")),
        "status": status,
        "status_line": status_line,
        "latest_failed_stage": latest_failed_stage,
        "latest_error_code": latest_error_code,
        "stage2_recovered": stage2_recovered,
        "stage2_ok_rows": _int(stage2.get("ok_rows")),
        "stage2_queue_rows": _int(stage2.get("queue_rows")),
        "stage2_writer_backpressure_count": _int(stage2.get("writer_backpressure_count")),
        "stage6_gate_failed": gate_failed,
        "gate_failed_metric_count": len(failed_metrics),
        "primary_gate_metric": primary_metric_name,
        "primary_gate_value": primary_metric_value,
        "primary_gate_threshold": primary_metric_threshold,
        "primary_gate_delta": primary_metric_delta,
        "primary_gate_source": _text(stage6.get("mean_min_distance_A_source")),
        "primary_gate_topk_k": _int(stage6.get("mean_min_distance_A_topk_k")),
        "min_frames_observed": _int(stage6.get("min_frames_observed")),
        "ranking_auc": _float(stage6.get("ranking_auc")),
        "ranking_pr_auc": _float(stage6.get("ranking_pr_auc")),
        "ranking_ef1": _float(stage6.get("ranking_ef1")),
        "ranking_bedroc": _float(stage6.get("ranking_bedroc")),
        "ranking_ece": _float(stage6.get("ranking_ece")),
        "ranking_topk_hit_rate": _float(stage6.get("ranking_topk_hit_rate")),
        "ranking_positive_count": _int(stage6.get("ranking_positive_count")),
        "ranking_ood_positive_count": _int(stage6.get("ranking_ood_positive_count")),
        "ranking_pass_signal": (
            f"auc={_fmt_float(stage6.get('ranking_auc'))}; "
            f"pr_auc={_fmt_float(stage6.get('ranking_pr_auc'))}; "
            f"ef1={_fmt_float(stage6.get('ranking_ef1'))}; "
            f"bedroc={_fmt_float(stage6.get('ranking_bedroc'))}; "
            f"ece={_fmt_float(stage6.get('ranking_ece'))}; "
            f"topk_hit_rate={_fmt_float(stage6.get('ranking_topk_hit_rate'))}"
        ),
        "culprit_band_supported": bool(culprit_summary.get("culprit_band_supported")),
        "culprit_band_source_label": _text(culprit_summary.get("culprit_band_source_label")),
        "culprit_band_source_artifact": _text(culprit_summary.get("culprit_band_source_artifact")),
        "culprit_band_row_count": _int(culprit_summary.get("culprit_band_row_count")),
        "culprit_band_member_pass_count_at_current_gate": _int(
            culprit_summary.get("culprit_band_member_pass_count_at_current_gate")
        ),
        "culprit_band_member_total_count": _int(culprit_summary.get("culprit_band_member_total_count")),
        "culprit_band_member_pass_pct_at_current_gate": _float(
            culprit_summary.get("culprit_band_member_pass_pct_at_current_gate")
        ),
        "culprit_band_mean_distance_A": _float(culprit_summary.get("culprit_band_mean_distance_A")),
        "culprit_band_matches_primary_metric": bool(culprit_summary.get("culprit_band_matches_primary_metric")),
        "culprit_band_worst_key": _text(culprit_summary.get("culprit_band_worst_key")),
        "culprit_band_worst_distance_A": _float(culprit_summary.get("culprit_band_worst_distance_A")),
        "culprit_band_worst_delta_A": _float(culprit_summary.get("culprit_band_worst_delta_A")),
        "threshold_candidate_count": _int(culprit_summary.get("threshold_candidate_count")),
        "execution_recommendation": execution_recommendation,
        "recent_transition_line": transition_line,
        "recent_stage6_fail_count": recent_stage6_fail_count,
        "recent_window_size": max(len(recent_nightly_payloads), 1),
        "next_required_step": next_required_step,
        "row_count": len(rows),
        "source_artifact_count": len(source_artifacts),
    }
    return {
        "summary": summary,
        "structured": {"source_artifacts": source_artifacts},
        "rows": rows,
    }


def _append_gate_failures(lines: list[str], rows: list[dict[str, Any]]) -> None:
    gate_rows = [row for row in rows if _text(row.get("row_kind")) == "gate_failure_metric"]
    lines.extend(
        [
            "## Gate Failures",
            "",
            "| rank | metric | value | threshold | delta_over_threshold | source | topk_k | stage2_recovered | ranking_auc | ranking_pr_auc | ranking_ef1 | ranking_topk_hit_rate | ranking_ece |",
            "| ---: | --- | ---: | ---: | ---: | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in gate_rows:
        lines.append(
            f"| {row['gate_rank']} | `{row['metric']}` | {row['value']:.3f} | {row['threshold']:.3f} | "
            f"{row['delta_over_threshold']:.3f} | `{row['source']}` | {row['topk_k']} | "
            f"`{row['stage2_recovered']}` | {row['ranking_auc']:.3f} | {row['ranking_pr_auc']:.3f} | "
            f"{row['ranking_ef1']:.3f} | {row['ranking_topk_hit_rate']:.3f} | {row['ranking_ece']:.3f} |"
        )


def _append_culprit_band(lines: list[str], payload: dict[str, Any]) -> None:
    summary = dict(payload.get("summary", {}) or {})
    culprit_rows = [row for row in (payload.get("rows", []) or []) if _text(row.get("row_kind")) == "culprit_band_member"]
    if not culprit_rows:
        return
    lines.extend(
        [
            "",
            "## Candidate Rows",
            "",
            f"- culprit_band_source: `{summary.get('culprit_band_source_label', '')}`",
            f"- culprit_band_mean_distance_A: `{_fmt_float(summary.get('culprit_band_mean_distance_A'))}`",
            f"- culprit_band_member_passes_at_current_gate: `{summary.get('culprit_band_member_pass_count_at_current_gate', 0)}/{summary.get('culprit_band_member_total_count', 0)}`",
            f"- culprit_band_worst_key: `{summary.get('culprit_band_worst_key', '')}`",
            "",
            "| band_rank | key | binder | score | calibrated_score | mean_min_distance_A | delta_vs_gate | mean_delta_contribution | replica_range_A | worst_replica_queue_id |",
            "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
        ]
    )
    for row in culprit_rows:
        replica_range = (
            f"{_fmt_float(row.get('replica_min_distance_A'))}-{_fmt_float(row.get('replica_max_distance_A'))}"
            if _float(row.get("replica_count")) > 0
            else "-"
        )
        lines.append(
            f"| {row['band_rank']} | `{row['band_key']}` | `{row['is_binder']}` | "
            f"{_fmt_float(row.get('score_value'))} | {_fmt_float(row.get('probability_score_value'))} | "
            f"{_fmt_float(row.get('mean_min_distance_A'))} | {_fmt_float(row.get('delta_vs_gate_threshold_A'))} | "
            f"{_fmt_float(row.get('mean_delta_contribution_A'))} | {replica_range} | "
            f"`{_text(row.get('worst_replica_queue_id')) or '-'}` |"
        )


def _append_threshold_candidates(lines: list[str], payload: dict[str, Any]) -> None:
    candidate_rows = [row for row in (payload.get("rows", []) or []) if _text(row.get("row_kind")) == "threshold_candidate"]
    if not candidate_rows:
        return
    lines.extend(
        [
            "",
            "## Threshold Candidates",
            "",
            "| candidate_label | threshold_A | band_mean_delta_A | band_mean_pass | member_pass_count | member_pass_pct | worst_member_delta_A | notes |",
            "| --- | ---: | ---: | --- | ---: | ---: | ---: | --- |",
        ]
    )
    for row in candidate_rows:
        lines.append(
            f"| `{row['candidate_label']}` | {_fmt_float(row.get('candidate_threshold_A'))} | "
            f"{_fmt_float(row.get('band_mean_delta_A'))} | `{row.get('band_mean_pass')}` | "
            f"{row.get('member_pass_count', 0)}/{row.get('member_total_count', 0)} | "
            f"{_fmt_float(row.get('member_pass_pct'), 1)} | {_fmt_float(row.get('worst_member_delta_A'))} | "
            f"{_text(row.get('notes'))} |"
        )


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = dict(payload.get("summary", {}) or {})
    structured = dict(payload.get("structured", {}) or {})
    lines = [
        "# Nightly Gate Burndown Packet",
        "",
        f"- latest_failed_stage: `{summary['latest_failed_stage']}`",
        f"- latest_error_code: `{summary['latest_error_code']}`",
        f"- status: `{summary['status']}`",
        f"- status_line: `{summary['status_line']}`",
        f"- stage2_recovered: `{summary['stage2_recovered']}`",
        f"- stage2_ok_rows: `{summary['stage2_ok_rows']}/{summary['stage2_queue_rows']}`",
        f"- stage6_gate_failed: `{summary['stage6_gate_failed']}`",
        f"- primary_gate_metric: `{summary['primary_gate_metric']}`",
        f"- primary_gate_value: `{_fmt_float(summary['primary_gate_value'])}`",
        f"- primary_gate_threshold: `{_fmt_float(summary['primary_gate_threshold'])}`",
        f"- primary_gate_delta: `{_fmt_float(summary['primary_gate_delta'])}`",
        f"- primary_gate_source: `{summary['primary_gate_source']}`",
        f"- primary_gate_topk_k: `{summary['primary_gate_topk_k']}`",
        f"- culprit_band_source_label: `{summary['culprit_band_source_label']}`",
        f"- culprit_band_member_passes_at_current_gate: `{summary['culprit_band_member_pass_count_at_current_gate']}/{summary['culprit_band_member_total_count']}`",
        f"- culprit_band_worst_key: `{summary['culprit_band_worst_key']}`",
        f"- culprit_band_worst_distance_A: `{_fmt_float(summary['culprit_band_worst_distance_A'])}`",
        f"- execution_recommendation: {summary['execution_recommendation']}",
        f"- ranking_pass_signal: `{summary['ranking_pass_signal']}`",
        f"- recent_transition_line: `{summary['recent_transition_line']}`",
        f"- recent_stage6_fail_count: `{summary['recent_stage6_fail_count']}`",
        "",
        "## Recommended Action",
        "",
        f"- {summary['execution_recommendation']}",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
    ]
    _append_gate_failures(lines, payload.get("rows", []) or [])
    _append_culprit_band(lines, payload)
    _append_threshold_candidates(lines, payload)
    lines.extend(["", "## Source Artifacts", ""])
    for artifact in structured.get("source_artifacts", []) or []:
        lines.append(f"- `{artifact}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the latest nightly gate burndown packet.")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    latest_nightly_path = _discover_latest_top_nightly()
    latest_nightly_payload = _load_json(latest_nightly_path) if latest_nightly_path else {}
    latest_nightly_artifact = (
        str(latest_nightly_path.relative_to(ROOT)) if latest_nightly_path else "runs/ligand_htvs_nightly_latest_summary.json"
    )
    stage2_artifact = _resolve_existing_companion_artifact(latest_nightly_artifact, "_stage2_traj_summary.json")
    stage5_artifact = _resolve_existing_companion_artifact(latest_nightly_artifact, "_stage5_ranking_summary.json")
    recent_paths = _recent_top_nightly_paths(limit=3)
    payload = build_payload(
        latest_nightly_payload=latest_nightly_payload,
        latest_nightly_artifact=latest_nightly_artifact,
        stage2_payload=_maybe_load_json(stage2_artifact),
        stage2_artifact=stage2_artifact,
        stage5_payload=_maybe_load_json(stage5_artifact),
        stage5_artifact=stage5_artifact,
        recent_nightly_payloads=[_load_json(path) for path in recent_paths],
        recent_nightly_artifacts=[str(path.relative_to(ROOT)) for path in recent_paths],
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
