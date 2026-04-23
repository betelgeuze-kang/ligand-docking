#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd


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


def _compare(value: float, operator: str, threshold: float) -> bool:
    op = str(operator).strip()
    if op == "<=":
        return value <= threshold
    if op == ">=":
        return value >= threshold
    if op == "<":
        return value < threshold
    if op == ">":
        return value > threshold
    if op == "==":
        return abs(value - threshold) <= 1e-12
    raise ValueError(f"unsupported operator: {operator}")


def _read_core_gate_status(core_gate_json: str, strict_summary_json: str) -> Dict[str, Any]:
    status = {
        "core_gate_pass": None,
        "overflow_events_count": 0,
        "source": "",
    }

    core_src = str(core_gate_json).strip()
    strict_src = str(strict_summary_json).strip()

    if core_src:
        if os.path.exists(core_src):
            payload = _load_json(core_src)
            summary = payload.get("summary", {}) if isinstance(payload.get("summary"), dict) else {}
            status["core_gate_pass"] = bool(summary.get("pass", False))
            overflow_events = payload.get("overflow_events", [])
            if isinstance(overflow_events, list):
                status["overflow_events_count"] = int(len(overflow_events))
            status["source"] = "core_gate_json"
        else:
            status["core_gate_pass"] = False
            status["source"] = "core_gate_json_missing"

    if strict_src:
        if os.path.exists(strict_src):
            payload = _load_json(strict_src)
            summary = payload.get("summary", {}) if isinstance(payload.get("summary"), dict) else {}
            gates = payload.get("gates", {}) if isinstance(payload.get("gates"), dict) else {}
            acc = gates.get("accuracy_gate", {}) if isinstance(gates.get("accuracy_gate"), dict) else {}
            strict_pass = bool(summary.get("pass", False))
            strict_overflow = int(_safe_float(acc.get("overflow_events_count")) or 0)
            if status["core_gate_pass"] is None:
                status["core_gate_pass"] = strict_pass
            else:
                status["core_gate_pass"] = bool(status["core_gate_pass"] and strict_pass)
            status["overflow_events_count"] = max(int(status["overflow_events_count"]), strict_overflow)
            status["source"] = "strict_summary_json" if not core_src else "core_gate_json+strict_summary_json"
        else:
            if status["core_gate_pass"] is None:
                status["core_gate_pass"] = False
            status["source"] = "strict_summary_json_missing" if not core_src else "core_gate_json+strict_summary_json_missing"

    return status


def _load_labels(labels_json: str, manifest_csv: str) -> Tuple[Dict[str, float], List[Dict[str, Any]], int]:
    src = str(labels_json).strip()
    if src:
        payload = _load_json(src)
        summary = payload.get("summary", {}) if isinstance(payload.get("summary"), dict) else {}
        metrics = summary.get("metrics", {}) if isinstance(summary.get("metrics"), dict) else {}
        per_target = payload.get("per_target", [])
        overflow = int(_safe_float(summary.get("overflow_events_count")) or 0)
        metrics_out: Dict[str, float] = {}
        for k, v in metrics.items():
            fv = _safe_float(v)
            if fv is None:
                continue
            metrics_out[str(k)] = float(fv)
        if not isinstance(per_target, list):
            per_target = []
        return metrics_out, [r for r in per_target if isinstance(r, dict)], overflow

    # Fallback mode: read metric columns directly from manifest.
    if not manifest_csv:
        return {}, [], 0
    df = pd.read_csv(manifest_csv)
    if "target" not in df.columns:
        return {}, [], 0
    records = df.to_dict(orient="records")
    return {}, records, 0


def run_gate(args: argparse.Namespace) -> Dict[str, Any]:
    domain = str(args.domain).strip().lower()
    policy = _load_json(str(args.policy_json))
    domains = policy.get("domains", {}) if isinstance(policy.get("domains"), dict) else {}
    if domain not in domains:
        raise ValueError(f"domain '{domain}' not found in policy: {args.policy_json}")

    common = policy.get("common", {}) if isinstance(policy.get("common"), dict) else {}
    require_core = bool(common.get("require_core_gate_pass", True))
    fail_on_overflow = bool(common.get("fail_on_overflow_or_saturation", True))

    core_status = _read_core_gate_status(
        core_gate_json=str(getattr(args, "core_gate_json", "")),
        strict_summary_json=str(getattr(args, "strict_summary_json", "")),
    )
    labels_metrics, per_target_rows, labels_overflow = _load_labels(
        labels_json=str(args.labels_json),
        manifest_csv=str(args.manifest_csv),
    )

    domain_metrics = domains[domain].get("metrics", [])
    if not isinstance(domain_metrics, list) or len(domain_metrics) == 0:
        raise ValueError(f"policy domain has no metrics: {domain}")

    eval_rows: List[Dict[str, Any]] = []
    failed_metrics: List[Dict[str, Any]] = []
    failed_targets = set()

    per_target_df = pd.DataFrame(per_target_rows)
    if per_target_df.empty:
        per_target_df = pd.DataFrame(columns=["target"])
    if "target" not in per_target_df.columns:
        per_target_df["target"] = []
    per_target_df["target"] = per_target_df["target"].astype(str)

    for metric_spec in domain_metrics:
        if not isinstance(metric_spec, dict):
            continue
        metric = str(metric_spec.get("name", "")).strip()
        operator = str(metric_spec.get("operator", "<=")).strip()
        threshold = _safe_float(metric_spec.get("threshold"))
        if (not metric) or (threshold is None):
            continue

        # Per-target checks are the primary fail-fast signal.
        if metric in per_target_df.columns:
            vals = pd.to_numeric(per_target_df[metric], errors="coerce")
            for idx, obs in vals.items():
                target = str(per_target_df.iloc[int(idx)]["target"])
                if pd.isna(obs):
                    status = "missing"
                    passed = False
                else:
                    obs_f = float(obs)
                    passed = _compare(obs_f, operator, float(threshold))
                    status = "pass" if passed else "fail"
                eval_rows.append(
                    {
                        "scope": "per_target",
                        "domain": domain,
                        "target": target,
                        "metric": metric,
                        "operator": operator,
                        "threshold": float(threshold),
                        "observed": (None if pd.isna(obs) else float(obs)),
                        "status": status,
                        "pass": bool(passed),
                    }
                )
                if not passed:
                    failed_targets.add(target)
                    failed_metrics.append(
                        {
                            "scope": "domain",
                            "target": target,
                            "metric": metric,
                            "operator": operator,
                            "threshold": float(threshold),
                            "value": (None if pd.isna(obs) else float(obs)),
                        }
                    )
        else:
            # If per-target column is missing, check label summary metric if present.
            obs = labels_metrics.get(metric)
            if obs is None:
                eval_rows.append(
                    {
                        "scope": "summary",
                        "domain": domain,
                        "target": "all",
                        "metric": metric,
                        "operator": operator,
                        "threshold": float(threshold),
                        "observed": None,
                        "status": "missing",
                        "pass": False,
                    }
                )
                failed_targets.add("all")
                failed_metrics.append(
                    {
                        "scope": "domain",
                        "target": "all",
                        "metric": metric,
                        "operator": operator,
                        "threshold": float(threshold),
                        "value": None,
                    }
                )
            else:
                passed = _compare(float(obs), operator, float(threshold))
                eval_rows.append(
                    {
                        "scope": "summary",
                        "domain": domain,
                        "target": "all",
                        "metric": metric,
                        "operator": operator,
                        "threshold": float(threshold),
                        "observed": float(obs),
                        "status": "pass" if passed else "fail",
                        "pass": bool(passed),
                    }
                )
                if not passed:
                    failed_targets.add("all")
                    failed_metrics.append(
                        {
                            "scope": "domain",
                            "target": "all",
                            "metric": metric,
                            "operator": operator,
                            "threshold": float(threshold),
                            "value": float(obs),
                        }
                    )

    # Common checks.
    core_gate_pass = core_status.get("core_gate_pass")
    if require_core and (core_gate_pass is not True):
        failed_metrics.append(
            {
                "scope": "common",
                "target": "all",
                "metric": "core_gate_pass",
                "operator": "==",
                "threshold": 1.0,
                "value": 0.0,
            }
        )
        failed_targets.add("all")

    overflow_events_count = int(core_status.get("overflow_events_count", 0)) + int(labels_overflow)
    if fail_on_overflow and overflow_events_count > 0:
        failed_metrics.append(
            {
                "scope": "common",
                "target": "all",
                "metric": "overflow_or_saturation_events",
                "operator": "==",
                "threshold": 0.0,
                "value": float(overflow_events_count),
            }
        )
        failed_targets.add("all")

    gate_pass = len(failed_metrics) == 0
    out_df = pd.DataFrame(eval_rows)
    if out_df.empty:
        out_df = pd.DataFrame(
            columns=[
                "scope",
                "domain",
                "target",
                "metric",
                "operator",
                "threshold",
                "observed",
                "status",
                "pass",
            ]
        )

    payload = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "inputs": {
            "domain": domain,
            "manifest_csv": str(args.manifest_csv),
            "labels_json": str(args.labels_json),
            "policy_json": str(args.policy_json),
            "core_gate_json": str(getattr(args, "core_gate_json", "")),
            "strict_summary_json": str(getattr(args, "strict_summary_json", "")),
        },
        "summary": {
            "pass": bool(gate_pass),
            "domain": domain,
            "targets": int(per_target_df.shape[0]),
            "failed_targets": sorted(str(x) for x in failed_targets),
            "failed_metrics": failed_metrics,
            "core_gate_pass": bool(core_gate_pass is True),
            "overflow_events_count": int(overflow_events_count),
        },
        "core_status": core_status,
        "labels_summary_metrics": labels_metrics,
    }

    os.makedirs(os.path.dirname(str(args.out_json)) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(str(args.out_csv)) or ".", exist_ok=True)
    with open(str(args.out_json), "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    out_df.to_csv(str(args.out_csv), index=False)

    out_md = str(getattr(args, "out_md", "")).strip()
    if out_md:
        os.makedirs(os.path.dirname(out_md) or ".", exist_ok=True)
        lines = [
            f"# Special Case Gate ({domain})",
            "",
            f"- pass: `{payload['summary']['pass']}`",
            f"- core_gate_pass: `{payload['summary']['core_gate_pass']}`",
            f"- overflow_events_count: `{payload['summary']['overflow_events_count']}`",
            f"- failed_targets: `{payload['summary']['failed_targets']}`",
            f"- failed_metrics_count: `{len(payload['summary']['failed_metrics'])}`",
            "",
            f"- csv: `{args.out_csv}`",
            f"- json: `{args.out_json}`",
        ]
        with open(out_md, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    return payload


def build_parser() -> argparse.ArgumentParser:
    stamp = dt.date.today().isoformat()
    p = argparse.ArgumentParser(
        description="Validate special-case domain gate with fail-fast policy."
    )
    p.add_argument("--domain", type=str, required=True, choices=["metal", "dna", "membrane"])
    p.add_argument("--manifest-csv", type=str, required=True)
    p.add_argument("--labels-json", type=str, default="")
    p.add_argument(
        "--policy-json",
        type=str,
        default="config/special_case_gate_policy_v1_2026-02-18.json",
    )
    p.add_argument("--core-gate-json", type=str, default="")
    p.add_argument("--strict-summary-json", type=str, default="")
    p.add_argument("--out-json", type=str, default=f"runs/special_case_gate_{stamp}.json")
    p.add_argument("--out-csv", type=str, default=f"runs/special_case_gate_{stamp}.csv")
    p.add_argument("--out-md", type=str, default="")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = run_gate(args)
    print(json.dumps(payload.get("summary", {}), indent=2, ensure_ascii=False))
    print(f"Wrote JSON: {args.out_json}")
    print(f"Wrote CSV: {args.out_csv}")
    if str(getattr(args, "out_md", "")).strip():
        print(f"Wrote MD: {args.out_md}")
    if not bool(payload.get("summary", {}).get("pass", False)):
        sys.exit(2)


if __name__ == "__main__":
    main()
