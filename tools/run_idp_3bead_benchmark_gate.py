#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from typing import Any, Dict, Optional, Sequence

import numpy as np

from tools.idp_3bead_common import BRANCH_NAMES, STATE_NAMES
from tools.idp_residual_common import RANKING_HEAD_NAMES


def _read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _average_precision(y_true: np.ndarray, y_score: np.ndarray) -> float:
    if y_true.size == 0 or float(y_true.sum()) <= 0.0:
        return 0.0
    order = np.argsort(-y_score)
    y = y_true[order]
    tp = np.cumsum(y)
    fp = np.cumsum(1.0 - y)
    precision = tp / np.maximum(tp + fp, 1.0)
    return float((precision * y).sum() / max(float(y.sum()), 1.0))


def _subset_average_precision(
    rows: list[dict[str, Any]],
    *,
    true_key: str,
    score_key: str,
    allowed_branches: set[str],
) -> float:
    subset = [row for row in rows if str(row.get("branch_label", "")) in allowed_branches]
    y_true = np.asarray([float(row.get(true_key, 0.0)) for row in subset], dtype=np.float32)
    y_score = np.asarray([float(row.get(score_key, 0.0)) for row in subset], dtype=np.float32)
    return _average_precision(y_true, y_score)


def _macro_f1(true_labels: list[str], pred_labels: list[str], names: list[str]) -> float:
    f1s = []
    for name in names:
        tp = sum(1 for t, p in zip(true_labels, pred_labels) if t == name and p == name)
        fp = sum(1 for t, p in zip(true_labels, pred_labels) if t != name and p == name)
        fn = sum(1 for t, p in zip(true_labels, pred_labels) if t == name and p != name)
        denom = (2 * tp + fp + fn)
        f1s.append(float((2 * tp) / denom) if denom else 0.0)
    return float(sum(f1s) / max(len(f1s), 1))


def _pairwise_auc(rows: list[dict[str, Any]], true_key: str, pred_key: str) -> float:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get("split_group", row.get("target", ""))), []).append(row)
    total = 0.0
    correct = 0.0
    for group_rows in grouped.values():
        if len(group_rows) < 2:
            continue
        for i, left in enumerate(group_rows):
            for right in group_rows[i + 1:]:
                true_diff = float(left.get(true_key, 0.0)) - float(right.get(true_key, 0.0))
                if abs(true_diff) < 1e-8:
                    continue
                pred_diff = float(left.get(pred_key, 0.0)) - float(right.get(pred_key, 0.0))
                total += 1.0
                correct += 1.0 if (true_diff > 0.0) == (pred_diff > 0.0) else 0.0
    return float(correct / total) if total > 0.0 else 0.0


def _anchor_diagnostics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    metrics = [
        "rg_mean",
        "sasa_proxy_mean",
        "contact_persistence",
        "transient_helicity",
        "ensemble_diversity",
    ]
    payload: dict[str, Any] = {}
    for metric in metrics:
        vals = []
        for row in rows:
            err = float(row.get(f"baseline_anchor_{metric}_error", 0.0))
            lo = row.get(f"baseline_anchor_{metric}_lo")
            hi = row.get(f"baseline_anchor_{metric}_hi")
            if lo is None or hi is None:
                continue
            width = max(float(hi) - float(lo), 1e-6)
            vals.append(err / width)
        median = float(np.median(vals)) if vals else 0.0
        if median <= 0.20:
            status = "good"
        elif median <= 0.40:
            status = "warning"
        else:
            status = "bad"
        payload[metric] = {
            "median_normalized_error": median,
            "status": status,
            "count": len(vals),
        }
    return payload


def _row_physics_failures(row: dict[str, Any], gate_cfg: dict[str, Any]) -> list[str]:
    target_failures: list[str] = []
    branch_label = str(row.get("branch_label", ""))
    vh_min = float(gate_cfg.get("min_virtual_hbond_contacts_mean", 0.10))
    ac_min = float(gate_cfg.get("min_anti_collapse_force_mean", 0.01))
    if branch_label == "helix_tad":
        vh_min *= 1.10
    if branch_label == "aggregation_prone":
        ac_min *= 1.10
    if float(row.get("on_virtual_hbond_contacts_mean", 0.0)) < vh_min:
        target_failures.append("virtual_hbond_contacts_mean")
    if float(row.get("on_anti_collapse_force_mean", 0.0)) < ac_min:
        target_failures.append("anti_collapse_force_mean")
    overcollapse_rate = float(row.get("on_overcollapse_rate", 0.0))
    if overcollapse_rate > float(gate_cfg.get("max_overcollapse_rate", 0.35)):
        rg_mean = float(row.get("on_rg_mean", 0.0) or 0.0)
        rg_target = float(row.get("on_anti_collapse_rg_target_A", 0.0) or 0.0)
        anchor_hi = row.get("baseline_anchor_rg_mean_hi")
        # If the ensemble is still clearly expanded, treat this as an overspread /
        # bimodal-trajectory issue instead of a true over-collapse hotspot.
        expanded_vs_target = rg_target > 0.0 and rg_mean > 1.08 * rg_target
        expanded_vs_anchor = anchor_hi is not None and rg_mean > 1.03 * float(anchor_hi)
        if not (expanded_vs_target or expanded_vs_anchor):
            target_failures.append("overcollapse_rate")
    return target_failures


def _physics_summary(rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> dict[str, Any]:
    metric_counts: dict[str, int] = {}
    branch_counts: dict[str, int] = {}
    branch_metric_counts: dict[str, dict[str, int]] = {}
    hotspot_map: dict[str, dict[str, Any]] = {}
    for item in failures:
        target = str(item.get("target", "")).strip()
        split_group = str(item.get("split_group", target)).strip()
        branch = str(item.get("branch_label", "")).strip() or "unknown"
        condition_group = str(item.get("condition_group", "")).strip()
        metrics = [str(x) for x in item.get("metrics", []) if str(x).strip()]
        branch_counts[branch] = branch_counts.get(branch, 0) + 1
        branch_metric_counts.setdefault(branch, {})
        key = split_group or target
        hotspot = hotspot_map.setdefault(
            key,
            {
                "target": target,
                "split_group": split_group,
                "branch_label": branch,
                "failed_row_count": 0,
                "metrics": set(),
                "condition_groups": set(),
            },
        )
        hotspot["failed_row_count"] += 1
        if condition_group:
            hotspot["condition_groups"].add(condition_group)
        for metric in metrics:
            metric_counts[metric] = metric_counts.get(metric, 0) + 1
            branch_metric_counts[branch][metric] = branch_metric_counts[branch].get(metric, 0) + 1
            hotspot["metrics"].add(metric)

    anchor_diag = _anchor_diagnostics(rows)
    anchor_status_counts: dict[str, int] = {}
    for metric, payload in anchor_diag.items():
        status = str(payload.get("status", "unknown"))
        anchor_status_counts[status] = anchor_status_counts.get(status, 0) + 1

    hotspots = []
    for item in hotspot_map.values():
        hotspots.append(
            {
                "target": item["target"],
                "split_group": item["split_group"],
                "branch_label": item["branch_label"],
                "failed_row_count": int(item["failed_row_count"]),
                "metrics": sorted(item["metrics"]),
                "condition_groups": sorted(item["condition_groups"]),
            }
        )
    hotspots.sort(key=lambda x: (-int(x["failed_row_count"]), str(x["split_group"])))
    hardening_candidates = [
        item for item in hotspots if int(item["failed_row_count"]) >= 2 or "overcollapse_rate" in list(item["metrics"])
    ]
    return {
        "failed_row_count": int(len(failures)),
        "unique_hotspot_count": int(len(hotspots)),
        "metric_counts": metric_counts,
        "branch_counts": branch_counts,
        "branch_metric_counts": branch_metric_counts,
        "anchor_status_counts": anchor_status_counts,
        "hotspots": hotspots,
        "hardening_candidates": hardening_candidates,
    }


def _legacy_gate(rows: list[dict[str, Any]], gate_cfg: dict[str, Any]) -> dict[str, Any]:
    failures = []
    for row in rows:
        target_failures = []
        if float(row.get("on_mean_force", 0.0)) < float(gate_cfg.get("min_mean_force", 0.01)):
            target_failures.append("mean_force")
        if float(row.get("on_virtual_hbond_mean_distance_A", 0.0)) > float(gate_cfg.get("max_virtual_hbond_mean_distance_A", 4.2)):
            target_failures.append("virtual_hbond_mean_distance_A")
        target_failures.extend(_row_physics_failures(row, gate_cfg))
        if target_failures:
            failures.append(
                {
                    "target": row.get("target", ""),
                    "split_group": row.get("split_group", row.get("target", "")),
                    "condition_group": row.get("condition_group", ""),
                    "branch_label": row.get("branch_label", ""),
                    "metrics": target_failures,
                }
            )
    target_count = len(rows)
    pass_count = target_count - len(failures)
    pass_fraction = float(pass_count / max(target_count, 1))
    return {
        "mode": "legacy",
        "target_count": target_count,
        "pass_count": pass_count,
        "pass_fraction": pass_fraction,
        "failed_targets": failures,
        "pass": bool(pass_fraction >= float(gate_cfg.get("min_target_pass_fraction", 0.75)) and len(failures) <= int(gate_cfg.get("max_failed_targets", 0))),
        "anchor_diagnostics": _anchor_diagnostics(rows),
        "physics_summary": _physics_summary(rows, failures),
    }


def _branch_gate(rows: list[dict[str, Any]], gate_cfg: dict[str, Any]) -> dict[str, Any]:
    true_branch = [str(row.get("branch_label", "")) for row in rows]
    pred_branch = []
    for row in rows:
        weights = {name: float(row.get(f"branch_weight_{name}", 0.0)) for name in BRANCH_NAMES}
        pred_branch.append(max(weights.items(), key=lambda kv: kv[1])[0])
    true_state = [str(row.get("true_dominant_state", "expanded_disordered")) for row in rows]
    pred_state = [str(row.get("pred_state", "expanded_disordered")) for row in rows]
    llps_true = np.asarray([float(row.get("true_llps_flag", 0.0)) for row in rows], dtype=np.float32)
    llps_prob = np.asarray([float(row.get("pred_llps_prob", 0.0)) for row in rows], dtype=np.float32)
    agg_true = np.asarray([float(row.get("true_aggregation_flag", 0.0)) for row in rows], dtype=np.float32)
    agg_prob = np.asarray([float(row.get("pred_aggregation_prob", 0.0)) for row in rows], dtype=np.float32)
    llps_relevant_pr_auc = _subset_average_precision(
        rows,
        true_key="true_llps_flag",
        score_key="pred_llps_prob",
        allowed_branches={"llps_lcd", "helix_tad"},
    )
    aggregation_relevant_pr_auc = _subset_average_precision(
        rows,
        true_key="true_aggregation_flag",
        score_key="pred_aggregation_prob",
        allowed_branches={"aggregation_prone"},
    )

    classification_metrics = {
        "branch_macro_f1": _macro_f1(true_branch, pred_branch, BRANCH_NAMES),
        "branch_accuracy": float(sum(int(t == p) for t, p in zip(true_branch, pred_branch)) / max(len(rows), 1)),
        "dominant_state_accuracy": float(sum(int(t == p) for t, p in zip(true_state, pred_state)) / max(len(rows), 1)),
        "llps_flag_pr_auc": _average_precision(llps_true, llps_prob),
        "aggregation_flag_pr_auc": _average_precision(agg_true, agg_prob),
        "llps_relevant_pr_auc": llps_relevant_pr_auc,
        "aggregation_relevant_pr_auc": aggregation_relevant_pr_auc,
    }
    branch_state_consistent = 0
    for row, pred in zip(rows, pred_branch):
        state = str(row.get("pred_state", "expanded_disordered"))
        if pred == "aggregation_prone":
            ok = state in {"expanded_disordered", "compact_disordered", "sticky_condensed"}
        elif pred == "llps_lcd":
            ok = state in {"sticky_condensed", "helix_enriched"}
        elif pred == "helix_tad":
            ok = state == "helix_enriched"
        else:
            ok = False
        branch_state_consistent += int(ok)
    classification_metrics["branch_state_consistency"] = float(branch_state_consistent / max(len(rows), 1))
    ranking_metrics = {
        "compactness_rank_auc": _pairwise_auc(rows, "compactness_score", "pred_rank_compactness"),
        "helicity_rank_auc": _pairwise_auc(rows, "helicity_score", "pred_rank_helicity"),
        "condensation_rank_auc": _pairwise_auc(rows, "condensation_score", "pred_rank_condensation"),
    }
    failed_targets = []
    for row in rows:
        target_failures = _row_physics_failures(row, gate_cfg)
        if target_failures:
            failed_targets.append(
                {
                    "target": row.get("target", ""),
                    "split_group": row.get("split_group", row.get("target", "")),
                    "condition_group": row.get("condition_group", ""),
                    "branch_label": row.get("branch_label", ""),
                    "metrics": target_failures,
                }
            )
    branch_counts: dict[str, int] = {}
    for name in true_branch:
        branch_counts[name] = branch_counts.get(name, 0) + 1
    dominant_branch = max(branch_counts.items(), key=lambda kv: kv[1])[0] if branch_counts else ""
    single_branch_eval = bool(len(branch_counts) == 1 and len(rows) > 0)

    effective_thresholds = {
        "branch_metric": "branch_macro_f1",
        "min_branch_metric": float(gate_cfg.get("min_branch_macro_f1", 0.0)),
        "llps_metric": "llps_flag_pr_auc",
        "aggregation_metric": "aggregation_flag_pr_auc",
        "min_dominant_state_accuracy": float(gate_cfg.get("min_dominant_state_accuracy", 0.0)),
        "min_llps_flag_pr_auc": float(gate_cfg.get("min_llps_flag_pr_auc", 0.0)),
        "min_aggregation_flag_pr_auc": float(gate_cfg.get("min_aggregation_flag_pr_auc", 0.0)),
        "min_compactness_rank_auc": float(gate_cfg.get("min_compactness_rank_auc", 0.0)),
        "min_helicity_rank_auc": float(gate_cfg.get("min_helicity_rank_auc", 0.0)),
        "min_condensation_rank_auc": float(gate_cfg.get("min_condensation_rank_auc", 0.0)),
    }
    if (not single_branch_eval) and bool(gate_cfg.get("use_branch_conditioned_combined_metrics", True)):
        effective_thresholds["llps_metric"] = "llps_relevant_pr_auc"
        effective_thresholds["aggregation_metric"] = "aggregation_relevant_pr_auc"
    if single_branch_eval:
        effective_thresholds["branch_metric"] = "branch_accuracy"
        effective_thresholds["min_branch_metric"] = float(gate_cfg.get("min_single_branch_accuracy", 0.75))
        if dominant_branch == "aggregation_prone":
            effective_thresholds["min_llps_flag_pr_auc"] = float(gate_cfg.get("aggregation_branch_min_llps_flag_pr_auc", 0.0))
            effective_thresholds["min_helicity_rank_auc"] = float(gate_cfg.get("aggregation_branch_min_helicity_rank_auc", 0.0))
        elif dominant_branch == "llps_lcd":
            effective_thresholds["min_aggregation_flag_pr_auc"] = float(gate_cfg.get("llps_branch_min_aggregation_flag_pr_auc", 0.0))
            effective_thresholds["min_compactness_rank_auc"] = float(gate_cfg.get("llps_branch_min_compactness_rank_auc", effective_thresholds["min_compactness_rank_auc"]))
        elif dominant_branch == "helix_tad":
            effective_thresholds["min_llps_flag_pr_auc"] = float(gate_cfg.get("helix_branch_min_llps_flag_pr_auc", 0.0))
            effective_thresholds["min_aggregation_flag_pr_auc"] = float(gate_cfg.get("helix_branch_min_aggregation_flag_pr_auc", 0.0))

    branch_metric_name = str(effective_thresholds["branch_metric"])
    llps_metric_name = str(effective_thresholds["llps_metric"])
    aggregation_metric_name = str(effective_thresholds["aggregation_metric"])
    branch_metric_value = float(classification_metrics.get(branch_metric_name, 0.0))
    utility_gate_pass = bool(
        branch_metric_value >= float(effective_thresholds["min_branch_metric"])
        and classification_metrics["dominant_state_accuracy"] >= float(effective_thresholds["min_dominant_state_accuracy"])
        and float(classification_metrics.get(llps_metric_name, 0.0)) >= float(effective_thresholds["min_llps_flag_pr_auc"])
        and float(classification_metrics.get(aggregation_metric_name, 0.0)) >= float(effective_thresholds["min_aggregation_flag_pr_auc"])
        and ranking_metrics["compactness_rank_auc"] >= float(effective_thresholds["min_compactness_rank_auc"])
        and ranking_metrics["helicity_rank_auc"] >= float(effective_thresholds["min_helicity_rank_auc"])
        and ranking_metrics["condensation_rank_auc"] >= float(effective_thresholds["min_condensation_rank_auc"])
    )
    physics_gate_pass = bool(len(failed_targets) <= int(gate_cfg.get("max_failed_targets", 0)))
    pass_flag = bool(utility_gate_pass and physics_gate_pass)
    return {
        "mode": "branch_moe_v1",
        "target_count": len(rows),
        "gate_context": {
            "dominant_branch": dominant_branch,
            "single_branch_eval": single_branch_eval,
            "branch_counts": branch_counts,
            "effective_thresholds": effective_thresholds,
            "physics_gate_mode": str(gate_cfg.get("physics_gate_mode", "strict")),
        },
        "classification_metrics": classification_metrics,
        "ranking_metrics": ranking_metrics,
        "failed_targets": failed_targets,
        "anchor_diagnostics": _anchor_diagnostics(rows),
        "physics_summary": _physics_summary(rows, failed_targets),
        "utility_gate_pass": utility_gate_pass,
        "physics_gate_pass": physics_gate_pass,
        "pass": pass_flag,
    }


def gate(args: argparse.Namespace) -> Dict[str, Any]:
    eval_payload = _read_json(str(args.eval_json))
    cfg = _read_json(str(args.config_json))
    gate_cfg = dict(cfg.get("gate", {}))
    rows = list(eval_payload.get("targets", []))
    use_branch = bool(rows and any("pred_state" in row for row in rows) and any(f"branch_weight_{name}" in rows[0] for name in BRANCH_NAMES))
    payload = _branch_gate(rows, gate_cfg) if use_branch else _legacy_gate(rows, gate_cfg)
    payload.update({
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "config_json": str(args.config_json),
        "eval_json": str(args.eval_json),
    })

    out_json = str(args.out_json).strip() or f"/home/betelgeuze/분자동역학/runs/idp_3bead_gate_{dt.date.today().isoformat()}.json"
    out_md = str(args.out_md).strip() or f"/home/betelgeuze/분자동역학/runs/idp_3bead_gate_{dt.date.today().isoformat()}.md"
    os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    lines = ["# IDP 3-Bead Benchmark Gate", "", f"- mode: {payload['mode']}", f"- pass: {payload['pass']}", f"- target_count: {payload['target_count']}"]
    if payload["mode"] == "branch_moe_v1":
        lines.extend([
            f"- branch_macro_f1: {payload['classification_metrics']['branch_macro_f1']}",
            f"- dominant_state_accuracy: {payload['classification_metrics']['dominant_state_accuracy']}",
            f"- llps_flag_pr_auc: {payload['classification_metrics']['llps_flag_pr_auc']}",
            f"- aggregation_flag_pr_auc: {payload['classification_metrics']['aggregation_flag_pr_auc']}",
            f"- physics_failed_rows: {payload.get('physics_summary', {}).get('failed_row_count', 0)}",
            f"- physics_hotspots: {payload.get('physics_summary', {}).get('unique_hotspot_count', 0)}",
        ])
    else:
        lines.extend([
            f"- pass_count: {payload['pass_count']}",
            f"- pass_fraction: {payload['pass_fraction']}",
            f"- physics_failed_rows: {payload.get('physics_summary', {}).get('failed_row_count', 0)}",
            f"- physics_hotspots: {payload.get('physics_summary', {}).get('unique_hotspot_count', 0)}",
        ])
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    payload["out_json"] = out_json
    payload["out_md"] = out_md
    return payload


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Apply IDP benchmark gate to evaluator outputs.")
    p.add_argument("--config-json", type=str, required=True)
    p.add_argument("--eval-json", type=str, required=True)
    p.add_argument("--out-json", type=str, default="")
    p.add_argument("--out-md", type=str, default="")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = gate(args)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if not bool(payload.get("pass", False)):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
