#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from typing import Any, Dict, Optional, Sequence, Tuple

import pandas as pd

from core.definitions import ResearchConstants
from tools import build_experiment_consistency_metrics as experiment_builder
from tools import build_kinetics_equivalence_metrics as kinetics_builder
from tools import build_thermodynamics_equivalence_metrics as thermo_builder
from tools import evaluate_allatom_equivalence_gate as gate_eval


def _build_from_csv(
    *,
    domain: str,
    input_csv: str,
    out_prefix: str,
) -> Tuple[str, str, Dict[str, Any]]:
    domain_name = str(domain).strip().lower()
    base = str(out_prefix).strip()
    if not base:
        raise ValueError("out_prefix is required for metric build")

    out_json = f"{base}_{domain_name}.json"
    out_csv = f"{base}_{domain_name}.csv"

    if domain_name == "kinetics":
        args = kinetics_builder.build_parser().parse_args(
            [
                "--input-csv",
                str(input_csv),
                "--out-json",
                out_json,
                "--out-csv",
                out_csv,
            ]
        )
        payload = kinetics_builder.run_build(args)
        return out_json, out_csv, payload

    if domain_name == "thermo":
        args = thermo_builder.build_parser().parse_args(
            [
                "--input-csv",
                str(input_csv),
                "--out-json",
                out_json,
                "--out-csv",
                out_csv,
            ]
        )
        payload = thermo_builder.run_build(args)
        return out_json, out_csv, payload

    if domain_name == "experiment":
        args = experiment_builder.build_parser().parse_args(
            [
                "--input-csv",
                str(input_csv),
                "--out-json",
                out_json,
                "--out-csv",
                out_csv,
            ]
        )
        payload = experiment_builder.run_build(args)
        return out_json, out_csv, payload

    raise ValueError(f"unsupported domain: {domain}")


def _resolve_metrics_json(
    *,
    domain: str,
    direct_json: str,
    input_csv: str,
    out_prefix: str,
) -> Tuple[str, Optional[str], Optional[Dict[str, Any]]]:
    direct = str(direct_json).strip()
    if direct:
        return direct, None, None

    src = str(input_csv).strip()
    if not src:
        return "", None, None
    if not os.path.exists(src):
        raise FileNotFoundError(f"{domain} input csv not found: {src}")

    out_json, out_csv, payload = _build_from_csv(domain=domain, input_csv=src, out_prefix=out_prefix)
    return out_json, out_csv, payload


def run_pipeline(args: argparse.Namespace) -> Dict[str, Any]:
    stamp = dt.datetime.now().isoformat(timespec="seconds")
    expected_targets = int(args.expected_target_count)

    kinetics_json, kinetics_csv, kinetics_payload = _resolve_metrics_json(
        domain="kinetics",
        direct_json=str(args.kinetics_json),
        input_csv=str(args.kinetics_input_csv),
        out_prefix=str(args.intermediate_prefix),
    )
    thermo_json, thermo_csv, thermo_payload = _resolve_metrics_json(
        domain="thermo",
        direct_json=str(args.thermo_json),
        input_csv=str(args.thermo_input_csv),
        out_prefix=str(args.intermediate_prefix),
    )
    experiment_json, experiment_csv, experiment_payload = _resolve_metrics_json(
        domain="experiment",
        direct_json=str(args.experiment_json),
        input_csv=str(args.experiment_input_csv),
        out_prefix=str(args.intermediate_prefix),
    )

    gate_args = gate_eval.build_parser().parse_args(
        [
            "--policy-json",
            str(args.policy_json),
            "--strict-summary-json",
            str(args.strict_summary_json),
            "--accuracy-external-csv",
            str(args.accuracy_external_csv),
            "--thermo-json",
            str(thermo_json),
            "--kinetics-json",
            str(kinetics_json),
            "--experiment-json",
            str(experiment_json),
            "--expected-target-count",
            str(expected_targets),
            "--out-json",
            str(args.gate_out_json),
            "--out-csv",
            str(args.gate_out_csv),
        ]
    )
    gate_payload = gate_eval.run_gate(gate_args)
    gate_summary = gate_payload.get("summary", {}) if isinstance(gate_payload, dict) else {}

    summary = {
        "policy_version": str(gate_summary.get("policy_version", "")),
        "pass_core_gate": bool(gate_summary.get("pass_core_gate", False)),
        "claim_ready_for_allatom": bool(gate_summary.get("claim_ready_for_allatom", False)),
        "core_failed_metrics": int(gate_summary.get("core_failed_metrics", 0)),
        "core_missing_metrics": int(gate_summary.get("core_missing_metrics", 0)),
        "claim_failed_metrics": int(gate_summary.get("claim_failed_metrics", 0)),
        "claim_missing_metrics": int(gate_summary.get("claim_missing_metrics", 0)),
    }

    payload = {
        "generated_at_local": stamp,
        "inputs": {
            "policy_json": str(args.policy_json),
            "strict_summary_json": str(args.strict_summary_json),
            "accuracy_external_csv": str(args.accuracy_external_csv),
            "kinetics_json": str(args.kinetics_json),
            "kinetics_input_csv": str(args.kinetics_input_csv),
            "thermo_json": str(args.thermo_json),
            "thermo_input_csv": str(args.thermo_input_csv),
            "experiment_json": str(args.experiment_json),
            "experiment_input_csv": str(args.experiment_input_csv),
            "expected_target_count": expected_targets,
            "enforce_complete_claim": bool(args.enforce_complete_claim),
        },
        "summary": summary,
        "artifacts": {
            "gate_json": str(args.gate_out_json),
            "gate_csv": str(args.gate_out_csv),
            "kinetics_json": kinetics_json,
            "kinetics_csv": kinetics_csv,
            "thermo_json": thermo_json,
            "thermo_csv": thermo_csv,
            "experiment_json": experiment_json,
            "experiment_csv": experiment_csv,
        },
        "built_payloads": {
            "kinetics": kinetics_payload,
            "thermo": thermo_payload,
            "experiment": experiment_payload,
        },
        "gate_domain_summaries": gate_payload.get("domain_summaries", []),
        "gate_observed_sources": gate_payload.get("observed_sources", {}),
    }

    os.makedirs(os.path.dirname(str(args.out_json)) or ".", exist_ok=True)
    with open(str(args.out_json), "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    out_df = pd.DataFrame(
        [
            {
                "pass_core_gate": summary["pass_core_gate"],
                "claim_ready_for_allatom": summary["claim_ready_for_allatom"],
                "core_failed_metrics": summary["core_failed_metrics"],
                "core_missing_metrics": summary["core_missing_metrics"],
                "claim_failed_metrics": summary["claim_failed_metrics"],
                "claim_missing_metrics": summary["claim_missing_metrics"],
                "gate_json": str(args.gate_out_json),
                "gate_csv": str(args.gate_out_csv),
                "kinetics_json": kinetics_json,
                "thermo_json": thermo_json,
                "experiment_json": experiment_json,
            }
        ]
    )
    os.makedirs(os.path.dirname(str(args.out_csv)) or ".", exist_ok=True)
    out_df.to_csv(str(args.out_csv), index=False)

    lines = [
        "# All-Atom Claim Readiness",
        "",
        f"- generated_at: {stamp}",
        f"- pass_core_gate: {summary['pass_core_gate']}",
        f"- claim_ready_for_allatom: {summary['claim_ready_for_allatom']}",
        f"- core_failed_metrics: {summary['core_failed_metrics']}",
        f"- core_missing_metrics: {summary['core_missing_metrics']}",
        f"- claim_failed_metrics: {summary['claim_failed_metrics']}",
        f"- claim_missing_metrics: {summary['claim_missing_metrics']}",
        "",
        "## Artifacts",
        f"- gate_json: {args.gate_out_json}",
        f"- gate_csv: {args.gate_out_csv}",
        f"- kinetics_json: {kinetics_json or '(none)'}",
        f"- thermo_json: {thermo_json or '(none)'}",
        f"- experiment_json: {experiment_json or '(none)'}",
    ]
    os.makedirs(os.path.dirname(str(args.out_md)) or ".", exist_ok=True)
    with open(str(args.out_md), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return payload


def build_parser() -> argparse.ArgumentParser:
    stamp = dt.date.today().isoformat()
    default_prefix = f"runs/allatom_claim_readiness_{stamp}"

    p = argparse.ArgumentParser(
        description=(
            "One-command all-atom claim readiness pipeline: "
            "build optional kinetics/thermo/experiment metrics and evaluate policy gate."
        )
    )
    p.add_argument(
        "--policy-json",
        type=str,
        default="config/allatom_equivalence_acceptance_v1_2026-02-17.json",
    )
    p.add_argument("--strict-summary-json", type=str, required=True)
    p.add_argument("--accuracy-external-csv", type=str, required=True)

    p.add_argument("--kinetics-json", type=str, default="")
    p.add_argument("--kinetics-input-csv", type=str, default="")
    p.add_argument("--thermo-json", type=str, default="")
    p.add_argument("--thermo-input-csv", type=str, default="")
    p.add_argument("--experiment-json", type=str, default="")
    p.add_argument("--experiment-input-csv", type=str, default="")

    p.add_argument("--expected-target-count", type=int, default=len(ResearchConstants.CHALLENGES))
    p.add_argument("--enforce-complete-claim", action=argparse.BooleanOptionalAction, default=False)

    p.add_argument("--intermediate-prefix", type=str, default=default_prefix)
    p.add_argument("--gate-out-json", type=str, default=f"{default_prefix}_gate.json")
    p.add_argument("--gate-out-csv", type=str, default=f"{default_prefix}_gate.csv")
    p.add_argument("--out-json", type=str, default=f"{default_prefix}_summary.json")
    p.add_argument("--out-csv", type=str, default=f"{default_prefix}_summary.csv")
    p.add_argument("--out-md", type=str, default=f"{default_prefix}_summary.md")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = run_pipeline(args)
    summary = payload.get("summary", {})

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"Wrote JSON: {args.out_json}")
    print(f"Wrote CSV: {args.out_csv}")
    print(f"Wrote MD: {args.out_md}")

    if not bool(summary.get("pass_core_gate", False)):
        sys.exit(2)
    if bool(args.enforce_complete_claim) and (not bool(summary.get("claim_ready_for_allatom", False))):
        sys.exit(2)


if __name__ == "__main__":
    main()
