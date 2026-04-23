#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import statistics
import subprocess
import sys
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd


def _run_cmd(cmd: List[str], env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    proc = subprocess.run(cmd, env=env, text=True, capture_output=True)
    return {
        "cmd": cmd,
        "cmd_str": " ".join(cmd),
        "returncode": int(proc.returncode),
        "ok": bool(proc.returncode == 0),
        "stdout_tail": "\n".join((proc.stdout or "").splitlines()[-60:]),
        "stderr_tail": "\n".join((proc.stderr or "").splitlines()[-60:]),
    }


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"invalid json object: {path}")
    return payload


def _safe_float(v: Any) -> float:
    try:
        return float(v)
    except Exception:
        return float("nan")


def _parse_int_csv(spec: str) -> List[int]:
    out: List[int] = []
    for tok in str(spec).split(","):
        tok = tok.strip()
        if not tok:
            continue
        out.append(int(tok))
    if not out:
        raise ValueError("seed list is empty")
    return out


def _default_date_tag() -> str:
    return dt.date.today().isoformat()


def run_repro(args: argparse.Namespace) -> Dict[str, Any]:
    date_tag = str(args.date_tag or _default_date_tag())
    seeds = _parse_int_csv(args.seeds)

    os.makedirs("runs", exist_ok=True)
    env = os.environ.copy()
    env["FORCE_RUST_HIP"] = "1"
    env["RUST_HIP_USE_GPU_NBLIST_BUILDER"] = "1"

    rows: List[Dict[str, Any]] = []
    command_logs: List[Dict[str, Any]] = []

    for i, seed_base in enumerate(seeds, start=1):
        target_seed = int(args.target_seed_base) + (i - 1)
        rep_tag = f"{date_tag}_rep{i}_s{seed_base}"
        rebench_prefix = f"runs/noncyclic_speed_accuracy_rebench_repro_{rep_tag}"

        rebench_cmd = [
            sys.executable,
            "tools/run_openmm_2bead_rebench.py",
            "--targets",
            str(args.targets),
            "--date-tag",
            rep_tag,
            "--skip-openmm-generate",
            "--external-manifest",
            str(args.external_manifest),
            "--stability-profile-json",
            str(args.profile_json),
            "--enforce-long-stability-gate",
            "--stability-runs",
            "1",
            "--stability-steps",
            str(int(args.stability_steps)),
            "--stability-checkpoints",
            str(args.stability_checkpoints),
            "--accuracy-steps",
            str(int(args.accuracy_steps)),
            "--accuracy-runs",
            str(int(args.accuracy_runs)),
            "--accuracy-noise",
            str(float(args.accuracy_noise)),
            "--seed-base",
            str(int(seed_base)),
            "--target-seed",
            str(int(target_seed)),
            "--with-fallback",
            "--force-rust",
            "--skip-speed-rebench",
            "--out-prefix",
            rebench_prefix,
        ]
        rec_rebench = _run_cmd(rebench_cmd, env=env)
        command_logs.append({"replicate": i, "stage": "rebench", **rec_rebench})
        if not rec_rebench["ok"]:
            raise RuntimeError(f"rebench failed at replicate {i}: {rec_rebench['returncode']}")

        speed_acc_json = f"{rebench_prefix}_speed_accuracy.json"
        acc_csv = f"{rebench_prefix}_accuracy.csv"
        payload = _load_json(speed_acc_json)
        merged = payload.get("merged_summary", {}) if isinstance(payload.get("merged_summary"), dict) else {}
        long_sum = (
            payload.get("long_stability_summary", {})
            if isinstance(payload.get("long_stability_summary"), dict)
            else {}
        )

        claim_prefix = f"runs/claim_metric_correction_loop_repro_{rep_tag}"
        claim_cmd = [
            sys.executable,
            "tools/run_claim_metric_correction_loop.py",
            "--policy-json",
            str(args.claim_policy_json),
            "--strict-summary-json",
            str(args.strict_summary_json),
            "--accuracy-external-csv",
            acc_csv,
            "--thermo-input-csv",
            str(args.thermo_input_csv),
            "--kinetics-input-csv",
            str(args.kinetics_input_csv),
            "--experiment-input-csv",
            str(args.experiment_input_csv),
            "--max-iters",
            str(int(args.claim_max_iters)),
            "--target-margin",
            str(float(args.claim_target_margin)),
            "--damping",
            str(float(args.claim_damping)),
            "--out-prefix",
            claim_prefix,
            "--enforce-complete-claim",
        ]
        rec_claim = _run_cmd(claim_cmd, env=env)
        command_logs.append({"replicate": i, "stage": "claim_correction", **rec_claim})
        if not rec_claim["ok"]:
            raise RuntimeError(f"claim correction failed at replicate {i}: {rec_claim['returncode']}")

        claim_summary_path = f"{claim_prefix}_summary.json"
        claim_summary = _load_json(claim_summary_path).get("summary", {})
        if not isinstance(claim_summary, dict):
            claim_summary = {}

        rows.append(
            {
                "replicate": int(i),
                "seed_base": int(seed_base),
                "target_seed": int(target_seed),
                "rebench_prefix": rebench_prefix,
                "accuracy_csv": acc_csv,
                "speed_accuracy_json": speed_acc_json,
                "avg_rmsd_aligned_vs_external": _safe_float(merged.get("avg_rmsd_aligned_vs_external")),
                "avg_rmsd_vs_native_aligned": _safe_float(merged.get("avg_rmsd_vs_native_aligned")),
                "long_stability_gate_pass": bool(long_sum.get("gate_pass", False)),
                "long_stability_failed_targets": ",".join(
                    [str(x) for x in (long_sum.get("failed_targets", []) or [])]
                ),
                "claim_summary_json": claim_summary_path,
                "claim_ready_for_allatom": bool(claim_summary.get("claim_ready_for_allatom", False)),
                "claim_failed_metrics_after_runner": int(
                    claim_summary.get("claim_failed_metrics_after_runner", -1)
                ),
            }
        )

    df = pd.DataFrame(rows)
    values = [float(x) for x in df["avg_rmsd_vs_native_aligned"].tolist() if not math.isnan(float(x))]
    mean_val = float(statistics.mean(values)) if values else float("nan")
    std_val = float(statistics.pstdev(values)) if len(values) > 1 else 0.0

    all_claim_ready = bool(df["claim_ready_for_allatom"].all()) if not df.empty else False
    all_stability_pass = bool(df["long_stability_gate_pass"].all()) if not df.empty else False
    std_ok = bool(std_val <= float(args.max_std_rmsd_vs_native_aligned))

    summary = {
        "date_tag": date_tag,
        "replicates": int(len(df)),
        "targets": str(args.targets),
        "profile_json": str(args.profile_json),
        "strict_summary_json": str(args.strict_summary_json),
        "all_claim_ready_for_allatom": all_claim_ready,
        "all_long_stability_pass": all_stability_pass,
        "avg_rmsd_vs_native_aligned_mean": mean_val,
        "avg_rmsd_vs_native_aligned_std": std_val,
        "max_std_rmsd_vs_native_aligned": float(args.max_std_rmsd_vs_native_aligned),
        "std_gate_pass": std_ok,
        "pass": bool(all_claim_ready and all_stability_pass and std_ok),
    }

    os.makedirs(os.path.dirname(str(args.out_csv)) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(str(args.out_json)) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(str(args.out_commands_json)) or ".", exist_ok=True)
    df.to_csv(str(args.out_csv), index=False)
    with open(str(args.out_json), "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "rows": rows}, f, indent=2, ensure_ascii=False)
    with open(str(args.out_commands_json), "w", encoding="utf-8") as f:
        json.dump(command_logs, f, indent=2, ensure_ascii=False)

    return {"summary": summary, "rows": rows, "command_logs": command_logs}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Run accuracy-first reproducibility checks (multi-seed) with long-stability + claim correction."
        )
    )
    p.add_argument("--date-tag", type=str, default="")
    p.add_argument("--seeds", type=str, default="1234,1235,1236")
    p.add_argument("--target-seed-base", type=int, default=42)
    p.add_argument("--targets", type=str, default="all")
    p.add_argument("--external-manifest", type=str, default="runs/real_md_source_manifest_openmm_2bead_2026-02-17.csv")
    p.add_argument("--profile-json", type=str, default="config/long_stability_target_tuned_all10_2026-02-17_v2.json")
    p.add_argument("--strict-summary-json", type=str, default="runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_summary.json")
    p.add_argument("--claim-policy-json", type=str, default="config/allatom_equivalence_acceptance_v1_2026-02-17.json")
    p.add_argument("--thermo-input-csv", type=str, default="runs/thermo_equivalence_input_real_openmm_nightly_accuracy_first_full_v2_2026-02-18.csv")
    p.add_argument("--kinetics-input-csv", type=str, default="runs/kinetics_equivalence_input_real_openmm_nightly_accuracy_first_full_v2_2026-02-18.csv")
    p.add_argument("--experiment-input-csv", type=str, default="runs/experiment_consistency_input_real_openmm_nightly_accuracy_first_full_v2_2026-02-18.csv")
    p.add_argument("--stability-steps", type=int, default=1200)
    p.add_argument("--stability-checkpoints", type=str, default="0,100,300,600,900,1200")
    p.add_argument("--accuracy-steps", type=int, default=60)
    p.add_argument("--accuracy-runs", type=int, default=3)
    p.add_argument("--accuracy-noise", type=float, default=0.02)
    p.add_argument("--claim-max-iters", type=int, default=10)
    p.add_argument("--claim-target-margin", type=float, default=0.9)
    p.add_argument("--claim-damping", type=float, default=0.75)
    p.add_argument("--max-std-rmsd-vs-native-aligned", type=float, default=0.01)
    stamp = dt.date.today().isoformat()
    p.add_argument("--out-csv", type=str, default=f"runs/accuracy_first_repro_{stamp}.csv")
    p.add_argument("--out-json", type=str, default=f"runs/accuracy_first_repro_{stamp}.json")
    p.add_argument("--out-commands-json", type=str, default=f"runs/accuracy_first_repro_{stamp}_commands.json")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = run_repro(args)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))
    print(f"Wrote CSV: {args.out_csv}")
    print(f"Wrote JSON: {args.out_json}")
    print(f"Wrote command log: {args.out_commands_json}")
    if not bool(payload["summary"].get("pass", False)):
        sys.exit(2)


if __name__ == "__main__":
    main()
