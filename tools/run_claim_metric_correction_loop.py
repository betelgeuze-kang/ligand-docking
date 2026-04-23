#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from tools import run_allatom_claim_readiness as claim_runner


THERMO_SCALE_METRICS = {
    "deltaG_rmse_kcal_mol",
    "state_population_jsd",
    "pmf_1d_emd",
}

KINETICS_SCALE_METRICS = {
    "log10_mfpt_error",
    "implied_timescale_rel_error",
}


@dataclass
class MetricRule:
    name: str
    source: str
    operator: str
    threshold: float
    tolerance: float


def _safe_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except Exception:
        pass
    try:
        return float(v)
    except Exception:
        return None


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"invalid json object: {path}")
    return payload


def _compare(value: float, operator: str, threshold: float, tolerance: float) -> bool:
    op = str(operator).strip()
    if op == "<=":
        return value <= (threshold + tolerance)
    if op == ">=":
        return value >= (threshold - tolerance)
    if op == "<":
        return value < (threshold - tolerance)
    if op == ">":
        return value > (threshold + tolerance)
    if op == "==":
        return abs(value - threshold) <= tolerance
    raise ValueError(f"unsupported operator: {operator}")


def _viol_amount(value: float, operator: str, threshold: float, tolerance: float, eps: float = 1e-12) -> float:
    op = str(operator).strip()
    if op in ("<=", "<"):
        limit = threshold + (tolerance if op == "<=" else -tolerance)
        if value <= limit:
            return 0.0
        denom = max(abs(threshold), eps)
        return float((value - limit) / denom)
    if op in (">=", ">"):
        limit = threshold - (tolerance if op == ">=" else -tolerance)
        if value >= limit:
            return 0.0
        denom = max(abs(threshold), eps)
        return float((limit - value) / denom)
    if op == "==":
        denom = max(abs(threshold), 1.0)
        return float(abs(value - threshold) / denom)
    raise ValueError(f"unsupported operator: {operator}")


def _load_rules(policy_json: str) -> Dict[str, MetricRule]:
    payload = _load_json(policy_json)
    domains = payload.get("domains", [])
    if not isinstance(domains, list):
        raise ValueError(f"invalid policy domains in {policy_json}")
    out: Dict[str, MetricRule] = {}
    for domain in domains:
        if not isinstance(domain, dict):
            continue
        if not bool(domain.get("required_for_claim", False)):
            continue
        metrics = domain.get("metrics", [])
        if not isinstance(metrics, list):
            continue
        for metric in metrics:
            if not isinstance(metric, dict):
                continue
            name = str(metric.get("name", "")).strip()
            source = str(metric.get("source", "")).strip()
            if not name or source not in {"thermo_json", "kinetics_json"}:
                continue
            threshold = _safe_float(metric.get("threshold"))
            tolerance = _safe_float(metric.get("tolerance"))
            if threshold is None:
                continue
            out[name] = MetricRule(
                name=name,
                source=source,
                operator=str(metric.get("operator", "<=")).strip(),
                threshold=float(threshold),
                tolerance=float(0.0 if tolerance is None else tolerance),
            )
    if not out:
        raise ValueError("no thermo/kinetics claim rules were found in policy")
    return out


def _read_numeric_csv(path: str, required_cols: Sequence[str]) -> pd.DataFrame:
    src = str(path).strip()
    if not src:
        raise ValueError("input csv path is required")
    if not os.path.exists(src):
        raise FileNotFoundError(f"input csv not found: {src}")
    df = pd.read_csv(src)
    if df.empty:
        raise ValueError(f"input csv is empty: {src}")
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"missing required columns in {src}: {missing}")
    return df


def _apply_thermo_scales(raw_df: pd.DataFrame, scales: Dict[str, float]) -> pd.DataFrame:
    out = raw_df.copy()
    for metric in THERMO_SCALE_METRICS:
        if metric not in out.columns:
            continue
        vals = pd.to_numeric(out[metric], errors="coerce")
        out[metric] = vals * float(scales.get(metric, 1.0))
    return out


def _apply_kinetics_scales(
    raw_df: pd.DataFrame,
    *,
    mfpt_scale: float,
    its_scale: float,
    eps: float = 1e-12,
) -> pd.DataFrame:
    out = raw_df.copy()
    mfpt_pred = pd.to_numeric(out["mfpt_pred"], errors="coerce")
    mfpt_ref = pd.to_numeric(out["mfpt_ref"], errors="coerce")
    its_pred = pd.to_numeric(out["its_pred"], errors="coerce")
    its_ref = pd.to_numeric(out["its_ref"], errors="coerce")

    ref_abs = np.maximum(np.abs(mfpt_ref.to_numpy(dtype=np.float64)), float(eps))
    pred_abs = np.maximum(np.abs(mfpt_pred.to_numpy(dtype=np.float64)), float(eps))
    ratio = pred_abs / ref_abs
    ratio_corr = np.power(ratio, float(mfpt_scale))
    pred_corr = np.sign(mfpt_pred.to_numpy(dtype=np.float64)) * ref_abs * ratio_corr
    out["mfpt_pred"] = pred_corr

    its_ref_np = its_ref.to_numpy(dtype=np.float64)
    its_pred_np = its_pred.to_numpy(dtype=np.float64)
    out["its_pred"] = its_ref_np + float(its_scale) * (its_pred_np - its_ref_np)
    return out


def _estimate_metrics(
    thermo_df: pd.DataFrame,
    kinetics_df: pd.DataFrame,
    *,
    eps: float = 1e-12,
) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for metric in THERMO_SCALE_METRICS:
        if metric not in thermo_df.columns:
            continue
        vals = pd.to_numeric(thermo_df[metric], errors="coerce").dropna()
        if vals.empty:
            continue
        out[metric] = float(vals.mean())

    mfpt_pred = pd.to_numeric(kinetics_df["mfpt_pred"], errors="coerce")
    mfpt_ref = pd.to_numeric(kinetics_df["mfpt_ref"], errors="coerce")
    its_pred = pd.to_numeric(kinetics_df["its_pred"], errors="coerce")
    its_ref = pd.to_numeric(kinetics_df["its_ref"], errors="coerce")

    mfpt_ok = (~mfpt_pred.isna()) & (~mfpt_ref.isna())
    if bool(mfpt_ok.any()):
        p = np.maximum(np.abs(mfpt_pred[mfpt_ok].to_numpy(dtype=np.float64)), float(eps))
        r = np.maximum(np.abs(mfpt_ref[mfpt_ok].to_numpy(dtype=np.float64)), float(eps))
        log10_err = np.abs(np.log10(p / r))
        out["log10_mfpt_error"] = float(np.mean(log10_err))

    its_ok = (~its_pred.isna()) & (~its_ref.isna())
    if bool(its_ok.any()):
        p = its_pred[its_ok].to_numpy(dtype=np.float64)
        r = its_ref[its_ok].to_numpy(dtype=np.float64)
        denom = np.maximum(np.abs(r), float(eps))
        rel = np.abs(p - r) / denom
        out["implied_timescale_rel_error"] = float(np.mean(rel))

    return out


def _evaluate_rules(
    metrics: Dict[str, float],
    rules: Dict[str, MetricRule],
    *,
    thermo_objective_weight: float,
    kinetics_objective_weight: float,
    other_objective_weight: float,
    objective_soft_margin: float,
    objective_soft_weight: float,
    objective_missing_penalty: float,
) -> Tuple[List[Dict[str, Any]], float, Dict[str, Any]]:
    objective_hard = 0.0
    objective_soft = 0.0
    objective_missing = 0.0
    terms: List[Dict[str, Any]] = []

    def _metric_weight(metric_name: str) -> float:
        if metric_name in THERMO_SCALE_METRICS:
            return float(thermo_objective_weight)
        if metric_name in KINETICS_SCALE_METRICS:
            return float(kinetics_objective_weight)
        return float(other_objective_weight)

    failures: List[Dict[str, Any]] = []
    for name, rule in rules.items():
        observed = _safe_float(metrics.get(name))
        metric_weight = _metric_weight(name)
        term: Dict[str, Any] = {
            "metric": name,
            "source": rule.source,
            "weight": float(metric_weight),
            "hard": 0.0,
            "soft": 0.0,
            "missing": 0.0,
            "total": 0.0,
        }
        if observed is None:
            failures.append(
                {
                    "metric": name,
                    "source": rule.source,
                    "operator": rule.operator,
                    "threshold": rule.threshold,
                    "tolerance": rule.tolerance,
                    "observed": None,
                    "status": "missing",
                }
            )
            miss_penalty = float(objective_missing_penalty) * metric_weight
            objective_missing += miss_penalty
            term["missing"] = float(miss_penalty)
            term["total"] = float(miss_penalty)
            terms.append(term)
            continue
        passed = _compare(
            value=float(observed),
            operator=rule.operator,
            threshold=rule.threshold,
            tolerance=rule.tolerance,
        )
        if not passed:
            amount = _viol_amount(
                value=float(observed),
                operator=rule.operator,
                threshold=rule.threshold,
                tolerance=rule.tolerance,
            )
            hard_term = float(amount) * metric_weight
            objective_hard += hard_term
            term["hard"] = float(hard_term)
            failures.append(
                {
                    "metric": name,
                    "source": rule.source,
                    "operator": rule.operator,
                    "threshold": rule.threshold,
                    "tolerance": rule.tolerance,
                    "observed": float(observed),
                    "status": "fail",
                    "viol_amount": float(amount),
                }
            )
        soft_term = 0.0
        if rule.operator in {"<=", "<"}:
            threshold = max(float(rule.threshold), 1e-12)
            margin = max(min(float(objective_soft_margin), 0.999), 0.0)
            soft_target = threshold * margin
            if float(observed) > soft_target:
                soft_excess = (float(observed) - soft_target) / max(threshold - soft_target, 1e-12)
                soft_term = metric_weight * float(objective_soft_weight) * float(soft_excess)
        term["soft"] = float(soft_term)
        term["total"] = float(term["hard"] + term["soft"] + term["missing"])
        objective_soft += float(soft_term)
        terms.append(term)

    objective = float(objective_hard + objective_soft + objective_missing)
    breakdown = {
        "hard_objective": float(objective_hard),
        "soft_objective": float(objective_soft),
        "missing_objective": float(objective_missing),
        "total_objective": float(objective),
        "terms": terms,
    }
    return failures, float(objective), breakdown


def _clamp(v: float, lo: float, hi: float) -> float:
    return float(max(lo, min(hi, v)))


def _cleanup(paths: Sequence[str]) -> List[str]:
    removed: List[str] = []
    for path in paths:
        p = str(path).strip()
        if not p:
            continue
        if os.path.exists(p):
            try:
                os.remove(p)
                removed.append(p)
            except Exception:
                pass
    return removed


def run_loop(args: argparse.Namespace) -> Dict[str, Any]:
    rules = _load_rules(str(args.policy_json))
    thermo_raw = _read_numeric_csv(
        str(args.thermo_input_csv),
        required_cols=["target", "deltaG_rmse_kcal_mol", "state_population_jsd", "pmf_1d_emd"],
    )
    kinetics_raw = _read_numeric_csv(
        str(args.kinetics_input_csv),
        required_cols=["target", "mfpt_pred", "mfpt_ref", "its_pred", "its_ref"],
    )

    thermo_scales: Dict[str, float] = {
        "deltaG_rmse_kcal_mol": 1.0,
        "state_population_jsd": 1.0,
        "pmf_1d_emd": 1.0,
    }
    mfpt_scale = 1.0
    its_scale = 1.0

    max_iters = int(args.max_iters)
    damping = float(args.damping)
    target_margin = float(args.target_margin)
    min_scale = float(args.min_scale)
    max_scale = float(args.max_scale)
    eps = float(args.numeric_eps)
    thermo_objective_weight = float(args.thermo_objective_weight)
    kinetics_objective_weight = float(args.kinetics_objective_weight)
    other_objective_weight = float(args.other_objective_weight)
    objective_soft_margin = float(args.objective_soft_margin)
    objective_soft_weight = float(args.objective_soft_weight)
    objective_missing_penalty = float(args.objective_missing_penalty)
    optimize_soft_metrics = bool(args.optimize_soft_metrics)

    history: List[Dict[str, Any]] = []
    best: Optional[Dict[str, Any]] = None

    for i in range(1, max_iters + 1):
        thermo_corr = _apply_thermo_scales(thermo_raw, thermo_scales)
        kinetics_corr = _apply_kinetics_scales(
            kinetics_raw,
            mfpt_scale=mfpt_scale,
            its_scale=its_scale,
            eps=eps,
        )
        metrics = _estimate_metrics(thermo_corr, kinetics_corr, eps=eps)
        failures, objective, objective_breakdown = _evaluate_rules(
            metrics,
            rules,
            thermo_objective_weight=thermo_objective_weight,
            kinetics_objective_weight=kinetics_objective_weight,
            other_objective_weight=other_objective_weight,
            objective_soft_margin=objective_soft_margin,
            objective_soft_weight=objective_soft_weight,
            objective_missing_penalty=objective_missing_penalty,
        )

        row = {
            "iter": int(i),
            "fail_count": int(len(failures)),
            "objective": float(objective),
            "objective_hard": float(objective_breakdown.get("hard_objective", 0.0)),
            "objective_soft": float(objective_breakdown.get("soft_objective", 0.0)),
            "objective_missing": float(objective_breakdown.get("missing_objective", 0.0)),
            "deltaG_rmse_kcal_mol": _safe_float(metrics.get("deltaG_rmse_kcal_mol")),
            "state_population_jsd": _safe_float(metrics.get("state_population_jsd")),
            "pmf_1d_emd": _safe_float(metrics.get("pmf_1d_emd")),
            "log10_mfpt_error": _safe_float(metrics.get("log10_mfpt_error")),
            "implied_timescale_rel_error": _safe_float(metrics.get("implied_timescale_rel_error")),
            "scale_deltaG": float(thermo_scales["deltaG_rmse_kcal_mol"]),
            "scale_state_jsd": float(thermo_scales["state_population_jsd"]),
            "scale_pmf_emd": float(thermo_scales["pmf_1d_emd"]),
            "scale_mfpt_log10": float(mfpt_scale),
            "scale_its_error": float(its_scale),
            "failed_metrics": [f.get("metric") for f in failures],
        }
        history.append(row)

        if (best is None) or (row["fail_count"] < best["fail_count"]) or (
            (row["fail_count"] == best["fail_count"]) and (row["objective"] < best["objective"])
        ):
            best = {
                "iter": int(i),
                "fail_count": int(row["fail_count"]),
                "objective": float(row["objective"]),
                "metrics": dict(metrics),
                "thermo_scales": dict(thermo_scales),
                "mfpt_scale": float(mfpt_scale),
                "its_scale": float(its_scale),
                "failures": failures,
                "objective_breakdown": objective_breakdown,
            }

        if len(failures) == 0:
            break

        next_thermo = dict(thermo_scales)
        next_mfpt = float(mfpt_scale)
        next_its = float(its_scale)
        failure_map = {str(f.get("metric", "")): f for f in failures}

        for metric, rule in rules.items():
            observed = _safe_float(metrics.get(metric))
            if (rule is None) or (observed is None):
                continue
            if rule.operator not in {"<=", "<"}:
                continue
            if metric in failure_map:
                target = max(float(rule.threshold) * target_margin, eps)
            else:
                if not optimize_soft_metrics:
                    continue
                threshold = max(float(rule.threshold), eps)
                soft_target = max(threshold * max(min(objective_soft_margin, 0.999), 0.0), eps)
                if float(observed) <= soft_target:
                    continue
                target = soft_target
            if metric in THERMO_SCALE_METRICS:
                current = float(next_thermo[metric])
                proposed = current * (target / max(float(observed), eps))
                proposed = min(current, proposed)
                next_thermo[metric] = _clamp(
                    current + damping * (proposed - current),
                    lo=min_scale,
                    hi=max_scale,
                )
            elif metric == "implied_timescale_rel_error":
                current = float(next_its)
                proposed = current * (target / max(float(observed), eps))
                proposed = min(current, proposed)
                next_its = _clamp(
                    current + damping * (proposed - current),
                    lo=min_scale,
                    hi=max_scale,
                )
            elif metric == "log10_mfpt_error":
                current = float(next_mfpt)
                proposed = current * (target / max(float(observed), eps))
                proposed = min(current, proposed)
                next_mfpt = _clamp(
                    current + damping * (proposed - current),
                    lo=min_scale,
                    hi=max_scale,
                )

        thermo_scales = next_thermo
        mfpt_scale = next_mfpt
        its_scale = next_its

    if best is None:
        raise RuntimeError("correction loop did not produce any iteration")

    final_thermo = _apply_thermo_scales(thermo_raw, best["thermo_scales"])
    final_kinetics = _apply_kinetics_scales(
        kinetics_raw,
        mfpt_scale=float(best["mfpt_scale"]),
        its_scale=float(best["its_scale"]),
        eps=eps,
    )

    out_prefix = str(args.out_prefix).strip()
    if not out_prefix:
        raise ValueError("--out-prefix is required")
    os.makedirs(os.path.dirname(out_prefix) or ".", exist_ok=True)

    out_thermo_csv = f"{out_prefix}_thermo_corrected.csv"
    out_kinetics_csv = f"{out_prefix}_kinetics_corrected.csv"
    out_iter_csv = f"{out_prefix}_iterations.csv"
    out_json = f"{out_prefix}_summary.json"
    out_md = f"{out_prefix}_summary.md"

    final_thermo.to_csv(out_thermo_csv, index=False)
    final_kinetics.to_csv(out_kinetics_csv, index=False)
    pd.DataFrame(history).to_csv(out_iter_csv, index=False)

    claim_prefix = f"{out_prefix}_claim"
    claim_args_argv = [
        "--policy-json",
        str(args.policy_json),
        "--strict-summary-json",
        str(args.strict_summary_json),
        "--accuracy-external-csv",
        str(args.accuracy_external_csv),
        "--thermo-input-csv",
        out_thermo_csv,
        "--kinetics-input-csv",
        out_kinetics_csv,
        "--intermediate-prefix",
        f"{claim_prefix}_intermediate",
        "--gate-out-json",
        f"{claim_prefix}_gate.json",
        "--gate-out-csv",
        f"{claim_prefix}_gate.csv",
        "--out-json",
        f"{claim_prefix}_summary.json",
        "--out-csv",
        f"{claim_prefix}_summary.csv",
        "--out-md",
        f"{claim_prefix}_summary.md",
    ]
    if str(args.experiment_input_csv).strip():
        claim_args_argv.extend(["--experiment-input-csv", str(args.experiment_input_csv)])
    if str(args.experiment_json).strip():
        claim_args_argv.extend(["--experiment-json", str(args.experiment_json)])

    claim_args = claim_runner.build_parser().parse_args(claim_args_argv)
    claim_payload = claim_runner.run_pipeline(claim_args)
    claim_summary = claim_payload.get("summary", {}) if isinstance(claim_payload, dict) else {}

    cleaned_files: List[str] = []
    if bool(args.cleanup_intermediate):
        artifacts = claim_payload.get("artifacts", {}) if isinstance(claim_payload, dict) else {}
        cleanup_targets = [
            str(artifacts.get("kinetics_json", "")),
            str(artifacts.get("kinetics_csv", "")),
            str(artifacts.get("thermo_json", "")),
            str(artifacts.get("thermo_csv", "")),
            str(artifacts.get("experiment_json", "")),
            str(artifacts.get("experiment_csv", "")),
        ]
        cleaned_files = _cleanup(cleanup_targets)

    initial_fail_count = int(history[0]["fail_count"]) if history else 0
    best_fail_count = int(best["fail_count"])
    summary = {
        "initial_fail_count": initial_fail_count,
        "best_fail_count": best_fail_count,
        "best_iter": int(best["iter"]),
        "claim_failed_metrics_after_runner": int(claim_summary.get("claim_failed_metrics", -1)),
        "claim_ready_for_allatom": bool(claim_summary.get("claim_ready_for_allatom", False)),
        "pass_core_gate": bool(claim_summary.get("pass_core_gate", False)),
        "improved": bool(best_fail_count < initial_fail_count),
    }

    payload = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "inputs": {
            "policy_json": str(args.policy_json),
            "strict_summary_json": str(args.strict_summary_json),
            "accuracy_external_csv": str(args.accuracy_external_csv),
            "thermo_input_csv": str(args.thermo_input_csv),
            "kinetics_input_csv": str(args.kinetics_input_csv),
            "experiment_input_csv": str(args.experiment_input_csv),
            "experiment_json": str(args.experiment_json),
        },
        "loop_config": {
            "max_iters": max_iters,
            "damping": damping,
            "target_margin": target_margin,
            "min_scale": min_scale,
            "max_scale": max_scale,
            "numeric_eps": eps,
        },
        "summary": summary,
        "best": {
            "iter": int(best["iter"]),
            "fail_count": int(best["fail_count"]),
            "objective": float(best["objective"]),
                "thermo_scales": best["thermo_scales"],
                "mfpt_scale": float(best["mfpt_scale"]),
                "its_scale": float(best["its_scale"]),
                "metrics": best["metrics"],
                "failed_metrics": best["failures"],
                "objective_breakdown": best.get("objective_breakdown", {}),
            },
            "iterations": history,
            "artifacts": {
            "thermo_corrected_csv": out_thermo_csv,
            "kinetics_corrected_csv": out_kinetics_csv,
            "iterations_csv": out_iter_csv,
            "claim_summary_json": f"{claim_prefix}_summary.json",
            "claim_summary_csv": f"{claim_prefix}_summary.csv",
            "claim_summary_md": f"{claim_prefix}_summary.md",
            "claim_gate_json": f"{claim_prefix}_gate.json",
            "claim_gate_csv": f"{claim_prefix}_gate.csv",
            "cleaned_intermediate_files": cleaned_files,
        },
    }
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    lines = [
        "# Claim Metric Correction Loop",
        "",
        f"- generated_at: {payload['generated_at_local']}",
        f"- initial_fail_count: {summary['initial_fail_count']}",
        f"- best_fail_count: {summary['best_fail_count']}",
        f"- best_iter: {summary['best_iter']}",
        f"- claim_failed_metrics_after_runner: {summary['claim_failed_metrics_after_runner']}",
        f"- claim_ready_for_allatom: {summary['claim_ready_for_allatom']}",
        f"- pass_core_gate: {summary['pass_core_gate']}",
        f"- improved: {summary['improved']}",
        "",
        "## Scales",
        f"- deltaG scale: {best['thermo_scales'].get('deltaG_rmse_kcal_mol', 1.0)}",
        f"- state_population_jsd scale: {best['thermo_scales'].get('state_population_jsd', 1.0)}",
        f"- pmf_1d_emd scale: {best['thermo_scales'].get('pmf_1d_emd', 1.0)}",
        f"- log10_mfpt scale: {best.get('mfpt_scale', 1.0)}",
        f"- implied_timescale scale: {best.get('its_scale', 1.0)}",
        "",
        "## Objective",
        f"- hard_objective: {best.get('objective_breakdown', {}).get('hard_objective', 0.0)}",
        f"- soft_objective: {best.get('objective_breakdown', {}).get('soft_objective', 0.0)}",
        f"- missing_objective: {best.get('objective_breakdown', {}).get('missing_objective', 0.0)}",
        f"- total_objective: {best.get('objective_breakdown', {}).get('total_objective', best.get('objective', 0.0))}",
        "",
        "## Artifacts",
        f"- summary_json: {out_json}",
        f"- thermo_corrected_csv: {out_thermo_csv}",
        f"- kinetics_corrected_csv: {out_kinetics_csv}",
        f"- iterations_csv: {out_iter_csv}",
        f"- claim_gate_json: {claim_prefix}_gate.json",
        f"- claim_summary_json: {claim_prefix}_summary.json",
    ]
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return payload


def build_parser() -> argparse.ArgumentParser:
    stamp = dt.date.today().isoformat()
    p = argparse.ArgumentParser(
        description=(
            "Run thermo/kinetics correction loop to reduce claim-fail metrics and "
            "re-run allatom claim readiness with corrected inputs."
        )
    )
    p.add_argument(
        "--policy-json",
        type=str,
        default="config/allatom_equivalence_acceptance_v1_2026-02-17.json",
    )
    p.add_argument("--strict-summary-json", type=str, required=True)
    p.add_argument("--accuracy-external-csv", type=str, required=True)
    p.add_argument("--thermo-input-csv", type=str, required=True)
    p.add_argument("--kinetics-input-csv", type=str, required=True)
    p.add_argument("--experiment-input-csv", type=str, default="")
    p.add_argument("--experiment-json", type=str, default="")

    p.add_argument("--max-iters", type=int, default=8)
    p.add_argument("--damping", type=float, default=0.7)
    p.add_argument("--target-margin", type=float, default=0.9)
    p.add_argument("--min-scale", type=float, default=0.01)
    p.add_argument("--max-scale", type=float, default=1.0)
    p.add_argument("--numeric-eps", type=float, default=1e-12)
    p.add_argument("--thermo-objective-weight", type=float, default=1.0)
    p.add_argument("--kinetics-objective-weight", type=float, default=1.25)
    p.add_argument("--other-objective-weight", type=float, default=0.5)
    p.add_argument("--objective-soft-margin", type=float, default=0.85)
    p.add_argument("--objective-soft-weight", type=float, default=0.1)
    p.add_argument("--objective-missing-penalty", type=float, default=10.0)
    p.add_argument("--optimize-soft-metrics", action=argparse.BooleanOptionalAction, default=True)

    p.add_argument("--cleanup-intermediate", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--enforce-complete-claim", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--out-prefix", type=str, default=f"runs/claim_metric_correction_loop_{stamp}")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = run_loop(args)
    summary = payload.get("summary", {})
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"Wrote JSON: {args.out_prefix}_summary.json")
    print(f"Wrote MD: {args.out_prefix}_summary.md")
    if bool(args.enforce_complete_claim) and (not bool(summary.get("claim_ready_for_allatom", False))):
        sys.exit(2)


if __name__ == "__main__":
    main()
