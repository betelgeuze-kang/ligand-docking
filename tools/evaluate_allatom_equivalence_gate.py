#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd

from core.definitions import ResearchConstants


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"invalid json object: {path}")
    return payload


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


def _optional_metrics_json(path: str) -> Dict[str, float]:
    src = str(path).strip()
    if not src:
        return {}
    if not os.path.exists(src):
        return {}
    payload = _load_json(src)
    raw = payload.get("metrics", payload)
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, float] = {}
    for k, v in raw.items():
        fv = _safe_float(v)
        if fv is None:
            continue
        out[str(k)] = float(fv)
    return out


def _read_accuracy_means(path: str) -> Dict[str, float]:
    src = str(path).strip()
    if not src:
        return {}
    if not os.path.exists(src):
        return {}
    df = pd.read_csv(src)
    if df.empty:
        return {}

    out: Dict[str, float] = {}
    col_map = {
        "avg_rmsd_aligned_A": "avg_rmsd_aligned",
        "avg_rmsd_vs_native_aligned_A": "avg_rmsd_vs_native_aligned",
        "avg_rmsd_raw_A": "avg_rmsd_raw",
        "avg_rmsd_vs_native_raw_A": "avg_rmsd_vs_native_raw",
    }
    for metric_name, col in col_map.items():
        if col not in df.columns:
            continue
        vals = pd.to_numeric(df[col], errors="coerce").dropna()
        if vals.empty:
            continue
        out[metric_name] = float(vals.mean())
    return out


def _read_strict_summary_metrics(path: str, expected_targets: int) -> Dict[str, float]:
    payload = _load_json(path)
    gates = payload.get("gates", {}) if isinstance(payload.get("gates"), dict) else {}
    summary = payload.get("summary", {}) if isinstance(payload.get("summary"), dict) else {}
    acc = gates.get("accuracy_gate", {}) if isinstance(gates.get("accuracy_gate"), dict) else {}
    spd = gates.get("speed", {}) if isinstance(gates.get("speed"), dict) else {}
    stb = gates.get("long_stability", {}) if isinstance(gates.get("long_stability"), dict) else {}

    out: Dict[str, float] = {}
    mapping = {
        "avg_neighbor_jaccard": acc.get("avg_neighbor_jaccard"),
        "avg_e2e_rmse_raw": acc.get("avg_e2e_rmse_raw"),
        "avg_e2e_rel_rmse_clipped": acc.get("avg_e2e_rel_rmse_mean_clipped"),
        "avg_speedup_on_vs_off": spd.get("avg_speedup_on_vs_off"),
        "long_stability_passed_targets": stb.get("passed_targets"),
        "strict_target_count": summary.get("targets"),
    }
    for k, v in mapping.items():
        fv = _safe_float(v)
        if fv is None:
            continue
        out[k] = float(fv)

    # Inject expected target count as explicit metric for optional policies.
    out.setdefault("expected_target_count", float(expected_targets))
    return out


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


def _evaluate_domains(
    policy: Dict[str, Any],
    observed: Dict[str, Dict[str, float]],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    domains = policy.get("domains", [])
    if not isinstance(domains, list) or len(domains) == 0:
        raise ValueError("policy must contain non-empty domains list")

    rows: List[Dict[str, Any]] = []
    domain_summaries: List[Dict[str, Any]] = []

    core_failed = 0
    core_missing = 0
    claim_failed = 0
    claim_missing = 0

    for domain in domains:
        if not isinstance(domain, dict):
            continue
        d_name = str(domain.get("name", "")).strip() or "unknown_domain"
        req_core = bool(domain.get("required_for_core_gate", False))
        req_claim = bool(domain.get("required_for_claim", False))
        metrics = domain.get("metrics", [])
        if not isinstance(metrics, list):
            metrics = []

        d_failed = 0
        d_missing = 0
        d_total = 0

        for m in metrics:
            if not isinstance(m, dict):
                continue
            d_total += 1
            m_name = str(m.get("name", "")).strip()
            source = str(m.get("source", "")).strip()
            operator = str(m.get("operator", "<=")).strip()
            threshold = _safe_float(m.get("threshold"))
            tolerance = _safe_float(m.get("tolerance"))
            if threshold is None:
                threshold = 0.0
            if tolerance is None:
                tolerance = 0.0

            source_map = observed.get(source, {})
            observed_val = source_map.get(m_name) if isinstance(source_map, dict) else None

            status = "missing"
            passed = False
            if observed_val is not None:
                passed = _compare(
                    value=float(observed_val),
                    operator=operator,
                    threshold=float(threshold),
                    tolerance=float(tolerance),
                )
                status = "pass" if passed else "fail"

            if status == "missing":
                d_missing += 1
                if req_core:
                    core_missing += 1
                if req_claim:
                    claim_missing += 1
            elif not passed:
                d_failed += 1
                if req_core:
                    core_failed += 1
                if req_claim:
                    claim_failed += 1

            rows.append(
                {
                    "domain": d_name,
                    "metric": m_name,
                    "source": source,
                    "required_for_core_gate": req_core,
                    "required_for_claim": req_claim,
                    "operator": operator,
                    "threshold": float(threshold),
                    "tolerance": float(tolerance),
                    "observed": observed_val,
                    "status": status,
                    "pass": bool(passed),
                }
            )

        d_pass = (d_failed == 0) and (d_missing == 0)
        domain_summaries.append(
            {
                "domain": d_name,
                "required_for_core_gate": req_core,
                "required_for_claim": req_claim,
                "metrics_total": int(d_total),
                "metrics_failed": int(d_failed),
                "metrics_missing": int(d_missing),
                "pass": bool(d_pass),
            }
        )

    summary = {
        "domain_summaries": domain_summaries,
        "core_failed_metrics": int(core_failed),
        "core_missing_metrics": int(core_missing),
        "claim_failed_metrics": int(claim_failed),
        "claim_missing_metrics": int(claim_missing),
        "pass_core_gate": bool((core_failed == 0) and (core_missing == 0)),
        "claim_ready_for_allatom": bool((claim_failed == 0) and (claim_missing == 0)),
    }
    return rows, summary


def run_gate(args: argparse.Namespace) -> Dict[str, Any]:
    policy = _load_json(str(args.policy_json))

    strict_metrics = _read_strict_summary_metrics(
        path=str(args.strict_summary_json),
        expected_targets=int(args.expected_target_count),
    )
    accuracy_metrics = _read_accuracy_means(str(args.accuracy_external_csv))
    thermo_metrics = _optional_metrics_json(str(args.thermo_json))
    kinetics_metrics = _optional_metrics_json(str(args.kinetics_json))
    experiment_metrics = _optional_metrics_json(str(args.experiment_json))

    observed = {
        "strict_summary": strict_metrics,
        "accuracy_external_csv": accuracy_metrics,
        "thermo_json": thermo_metrics,
        "kinetics_json": kinetics_metrics,
        "experiment_json": experiment_metrics,
    }

    rows, gate_summary = _evaluate_domains(policy=policy, observed=observed)
    out_df = pd.DataFrame(rows)

    summary = {
        "policy_version": str(policy.get("version", "unknown")),
        "pass_core_gate": bool(gate_summary["pass_core_gate"]),
        "claim_ready_for_allatom": bool(gate_summary["claim_ready_for_allatom"]),
        "core_failed_metrics": int(gate_summary["core_failed_metrics"]),
        "core_missing_metrics": int(gate_summary["core_missing_metrics"]),
        "claim_failed_metrics": int(gate_summary["claim_failed_metrics"]),
        "claim_missing_metrics": int(gate_summary["claim_missing_metrics"]),
    }

    payload = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "inputs": {
            "policy_json": str(args.policy_json),
            "strict_summary_json": str(args.strict_summary_json),
            "accuracy_external_csv": str(args.accuracy_external_csv),
            "thermo_json": str(args.thermo_json),
            "kinetics_json": str(args.kinetics_json),
            "experiment_json": str(args.experiment_json),
            "expected_target_count": int(args.expected_target_count),
        },
        "summary": summary,
        "domain_summaries": gate_summary["domain_summaries"],
        "observed_sources": observed,
    }

    os.makedirs(os.path.dirname(str(args.out_json)) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(str(args.out_csv)) or ".", exist_ok=True)
    with open(str(args.out_json), "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    out_df.to_csv(str(args.out_csv), index=False)
    return payload


def build_parser() -> argparse.ArgumentParser:
    stamp = dt.date.today().isoformat()
    p = argparse.ArgumentParser(
        description="Evaluate all-atom-equivalence acceptance policy with core/claim readiness split."
    )
    p.add_argument(
        "--policy-json",
        type=str,
        default="config/allatom_equivalence_acceptance_v1_2026-02-17.json",
    )
    p.add_argument("--strict-summary-json", type=str, required=True)
    p.add_argument("--accuracy-external-csv", type=str, default="")
    p.add_argument("--thermo-json", type=str, default="")
    p.add_argument("--kinetics-json", type=str, default="")
    p.add_argument("--experiment-json", type=str, default="")
    p.add_argument("--expected-target-count", type=int, default=len(ResearchConstants.CHALLENGES))
    p.add_argument("--enforce-complete-claim", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--out-json", type=str, default=f"runs/allatom_equivalence_gate_{stamp}.json")
    p.add_argument("--out-csv", type=str, default=f"runs/allatom_equivalence_gate_{stamp}.csv")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = run_gate(args)
    summary = payload.get("summary", {})
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"Wrote JSON: {args.out_json}")
    print(f"Wrote CSV: {args.out_csv}")

    if not bool(summary.get("pass_core_gate", False)):
        sys.exit(2)
    if bool(args.enforce_complete_claim) and (not bool(summary.get("claim_ready_for_allatom", False))):
        sys.exit(2)


if __name__ == "__main__":
    main()

