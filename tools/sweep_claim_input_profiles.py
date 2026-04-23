#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import itertools
import json
import os
import subprocess
import sys
import glob
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd


def _run_cmd(cmd: List[str], env: Optional[Dict[str, str]] = None, dry_run: bool = False) -> Dict[str, Any]:
    rec: Dict[str, Any] = {
        "cmd": list(cmd),
        "cmd_str": " ".join(cmd),
        "dry_run": bool(dry_run),
        "returncode": 0,
        "ok": True,
        "stdout_tail": "",
        "stderr_tail": "",
    }
    if dry_run:
        return rec
    proc = subprocess.run(cmd, env=env, text=True, capture_output=True)
    rec["returncode"] = int(proc.returncode)
    rec["ok"] = bool(proc.returncode == 0)
    rec["stdout_tail"] = "\n".join((proc.stdout or "").splitlines()[-60:])
    rec["stderr_tail"] = "\n".join((proc.stderr or "").splitlines()[-60:])
    return rec


def _read_json(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _resolve_input_path(path: str) -> str:
    src = str(path).strip()
    if not src:
        return src
    if os.path.exists(src):
        return src
    base = os.path.basename(src)
    if not base:
        return src
    candidates = [p for p in glob.glob(f"runs/**/{base}", recursive=True) if os.path.isfile(p)]
    if not candidates:
        return src
    candidates = sorted(candidates, key=lambda p: os.path.getmtime(p))
    return str(candidates[-1])


def _parse_csv_tokens(spec: str) -> List[str]:
    vals = [x.strip() for x in str(spec).split(",") if x.strip()]
    if not vals:
        raise ValueError("empty list")
    return vals


def _parse_csv_ints(spec: str) -> List[int]:
    vals = [int(x.strip()) for x in str(spec).split(",") if x.strip()]
    if not vals:
        raise ValueError("empty int list")
    return vals


def _parse_csv_floats(spec: str) -> List[float]:
    vals = [float(x.strip()) for x in str(spec).split(",") if x.strip()]
    if not vals:
        raise ValueError("empty float list")
    return vals


def _parse_tail_clip_pairs(spec: str) -> List[Tuple[float, float]]:
    out: List[Tuple[float, float]] = []
    for tok in _parse_csv_tokens(spec):
        if ":" not in tok:
            raise ValueError(f"invalid tail clip pair: {tok}")
        lo_s, hi_s = tok.split(":", 1)
        lo = float(lo_s.strip())
        hi = float(hi_s.strip())
        if not (0.0 <= lo < hi <= 1.0):
            raise ValueError(f"invalid tail clip range: {tok}")
        out.append((lo, hi))
    return out


def _extract_failed_claim_metrics(gate_csv_path: str) -> List[str]:
    if not os.path.exists(gate_csv_path):
        return []
    try:
        df = pd.read_csv(gate_csv_path)
    except Exception:
        return []
    if df.empty or ("metric" not in df.columns) or ("pass" not in df.columns):
        return []
    req = df["required_for_claim"].astype(bool) if "required_for_claim" in df.columns else pd.Series([True] * len(df))
    failed = df[(req) & (~df["pass"].astype(bool))]
    metrics = [str(x) for x in failed["metric"].tolist() if str(x).strip()]
    return sorted(set(metrics))


def _safe_int(v: Any, default: int = -1) -> int:
    try:
        if v is None:
            return int(default)
        if isinstance(v, float) and pd.isna(v):
            return int(default)
        return int(v)
    except Exception:
        return int(default)


def _safe_str(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and pd.isna(v):
        return ""
    s = str(v).strip()
    return s


def _build_profiles(args: argparse.Namespace) -> List[Dict[str, Any]]:
    profiles: List[Dict[str, Any]] = []
    grid = itertools.product(
        _parse_csv_tokens(args.split_modes),
        _parse_csv_ints(args.split_replicas_list),
        _parse_csv_ints(args.split_window_frames_list),
        _parse_csv_ints(args.split_window_stride_list),
        _parse_csv_ints(args.min_effective_frames_list),
        _parse_csv_tokens(args.thermo_agg_methods),
        _parse_csv_tokens(args.kinetics_agg_methods),
        _parse_csv_tokens(args.experiment_agg_methods),
        _parse_csv_floats(args.trim_fractions),
        _parse_tail_clip_pairs(args.tail_clip_pairs),
        _parse_csv_floats(args.pmf_pseudocounts),
        _parse_csv_floats(args.kinetics_min_signal_stds),
        _parse_csv_floats(args.kinetics_min_denom_epss),
    )
    for idx, item in enumerate(grid, start=1):
        (
            split_mode,
            split_replicas,
            split_window_frames,
            split_window_stride,
            min_effective_frames,
            thermo_agg,
            kinetics_agg,
            experiment_agg,
            trim_fraction,
            tail_clip,
            pmf_pseudocount,
            kinetics_min_signal_std,
            kinetics_min_denom_eps,
        ) = item
        profiles.append(
            {
                "profile_index": int(idx),
                "split_mode": str(split_mode),
                "split_replicas": int(split_replicas),
                "split_window_frames": int(split_window_frames),
                "split_window_stride": int(split_window_stride),
                "min_effective_frames": int(min_effective_frames),
                "thermo_agg_method": str(thermo_agg),
                "kinetics_agg_method": str(kinetics_agg),
                "experiment_agg_method": str(experiment_agg),
                "trim_fraction": float(trim_fraction),
                "tail_clip_low": float(tail_clip[0]),
                "tail_clip_high": float(tail_clip[1]),
                "pmf_pseudocount": float(pmf_pseudocount),
                "kinetics_min_signal_std": float(kinetics_min_signal_std),
                "kinetics_min_denom_eps": float(kinetics_min_denom_eps),
            }
        )
        if len(profiles) >= int(args.max_profiles):
            break
    return profiles


def run_sweep(args: argparse.Namespace) -> Dict[str, Any]:
    os.makedirs(os.path.dirname(str(args.out_prefix)) or ".", exist_ok=True)
    profiles = _build_profiles(args)
    manifest_csv = _resolve_input_path(str(args.manifest_csv))
    strict_summary_json = _resolve_input_path(str(args.strict_summary_json))
    accuracy_external_csv = _resolve_input_path(str(args.accuracy_external_csv))
    policy_json = _resolve_input_path(str(args.policy_json))

    env = os.environ.copy()
    if bool(args.force_rust):
        env["FORCE_RUST_HIP"] = "1"
        env["RUST_HIP_USE_GPU_NBLIST_BUILDER"] = "1"

    rows: List[Dict[str, Any]] = []
    command_logs: List[Dict[str, Any]] = []

    for i, profile in enumerate(profiles, start=1):
        tag = f"p{i:03d}"
        claim_input_prefix = f"{args.out_prefix}_{tag}_claim_inputs"
        out_k = f"{claim_input_prefix}_kinetics.csv"
        out_t = f"{claim_input_prefix}_thermo.csv"
        out_e = f"{claim_input_prefix}_experiment.csv"
        out_d_csv = f"{claim_input_prefix}_diagnostics.csv"
        out_d_json = f"{claim_input_prefix}_diagnostics.json"
        out_ci_json = f"{claim_input_prefix}_summary.json"

        build_cmd: List[str] = [
            sys.executable,
            "tools/build_claim_inputs_from_openmm_manifest.py",
            "--manifest-csv",
            str(manifest_csv),
            "--targets",
            str(args.targets),
            "--out-kinetics-csv",
            out_k,
            "--out-thermo-csv",
            out_t,
            "--out-experiment-csv",
            out_e,
            "--out-diagnostics-csv",
            out_d_csv,
            "--out-diagnostics-json",
            out_d_json,
            "--out-json",
            out_ci_json,
            "--split-mode",
            str(profile["split_mode"]),
            "--split-replicas",
            str(int(profile["split_replicas"])),
            "--split-window-frames",
            str(int(profile["split_window_frames"])),
            "--split-window-stride",
            str(int(profile["split_window_stride"])),
            "--min-effective-frames",
            str(int(profile["min_effective_frames"])),
            "--thermo-agg-method",
            str(profile["thermo_agg_method"]),
            "--kinetics-agg-method",
            str(profile["kinetics_agg_method"]),
            "--experiment-agg-method",
            str(profile["experiment_agg_method"]),
            "--trim-fraction",
            str(float(profile["trim_fraction"])),
            "--tail-clip-low",
            str(float(profile["tail_clip_low"])),
            "--tail-clip-high",
            str(float(profile["tail_clip_high"])),
            "--pmf-pseudocount",
            str(float(profile["pmf_pseudocount"])),
            "--kinetics-min-signal-std",
            str(float(profile["kinetics_min_signal_std"])),
            "--kinetics-min-denom-eps",
            str(float(profile["kinetics_min_denom_eps"])),
        ]
        rec_build = _run_cmd(build_cmd, env=env, dry_run=bool(args.dry_run))
        rec_build["stage"] = "build_claim_inputs"
        rec_build["profile"] = tag
        command_logs.append(rec_build)

        claim_prefix = f"{args.out_prefix}_{tag}_claim"
        gate_out_json = f"{claim_prefix}_gate.json"
        gate_out_csv = f"{claim_prefix}_gate.csv"
        claim_out_json = f"{claim_prefix}_summary.json"
        claim_out_csv = f"{claim_prefix}_summary.csv"
        claim_out_md = f"{claim_prefix}_summary.md"

        rec_claim: Dict[str, Any] = {
            "ok": False,
            "returncode": 1,
            "stdout_tail": "",
            "stderr_tail": "",
            "cmd": [],
            "cmd_str": "",
            "dry_run": bool(args.dry_run),
            "stage": "run_allatom_claim_readiness",
            "profile": tag,
        }

        if bool(rec_build.get("ok", False)):
            claim_cmd = [
                sys.executable,
                "tools/run_allatom_claim_readiness.py",
                "--policy-json",
                str(policy_json),
                "--strict-summary-json",
                str(strict_summary_json),
                "--accuracy-external-csv",
                str(accuracy_external_csv),
                "--kinetics-input-csv",
                out_k,
                "--thermo-input-csv",
                out_t,
                "--experiment-input-csv",
                out_e,
                "--expected-target-count",
                str(int(args.expected_target_count)),
                "--intermediate-prefix",
                claim_prefix,
                "--gate-out-json",
                gate_out_json,
                "--gate-out-csv",
                gate_out_csv,
                "--out-json",
                claim_out_json,
                "--out-csv",
                claim_out_csv,
                "--out-md",
                claim_out_md,
            ]
            if bool(args.enforce_complete_claim):
                claim_cmd.append("--enforce-complete-claim")
            rec_claim = _run_cmd(claim_cmd, env=env, dry_run=bool(args.dry_run))
            rec_claim["stage"] = "run_allatom_claim_readiness"
            rec_claim["profile"] = tag
        command_logs.append(rec_claim)

        claim_payload = _read_json(claim_out_json) if (not bool(args.dry_run)) else {}
        claim_summary = claim_payload.get("summary", {}) if isinstance(claim_payload.get("summary"), dict) else {}
        diag_payload = _read_json(out_d_json) if (not bool(args.dry_run)) else {}
        diag_summary = diag_payload.get("summary", {}) if isinstance(diag_payload.get("summary"), dict) else {}

        claim_ready = bool(claim_summary.get("claim_ready_for_allatom", False)) if claim_summary else False
        claim_failed_metrics = int(claim_summary.get("claim_failed_metrics", -1)) if claim_summary else -1
        failed_metrics = _extract_failed_claim_metrics(gate_out_csv) if (not bool(args.dry_run)) else []

        row: Dict[str, Any] = {
            **profile,
            "profile_tag": tag,
            "build_ok": bool(rec_build.get("ok", False)),
            "claim_ok": bool(rec_claim.get("ok", False)),
            "claim_ready_for_allatom": bool(claim_ready),
            "claim_failed_metrics": int(claim_failed_metrics),
            "failed_claim_metrics": ",".join(failed_metrics),
            "diagnostics_targets_with_rows": int(diag_summary.get("targets_with_diagnostics", 0) or 0),
            "diagnostics_targets_failed": int(diag_summary.get("targets_failed", 0) or 0),
            "claim_summary_json": claim_out_json,
            "claim_gate_csv": gate_out_csv,
            "claim_inputs_summary_json": out_ci_json,
            "claim_inputs_diagnostics_json": out_d_json,
            "pass": bool(claim_ready and (claim_failed_metrics == 0) and rec_build.get("ok", False) and rec_claim.get("ok", False)),
        }
        rows.append(row)

        if bool(args.fail_fast) and (not bool(row["pass"])):
            break

    df = pd.DataFrame(rows)
    if not df.empty:
        df["rank_key_claim_failed"] = pd.to_numeric(df["claim_failed_metrics"], errors="coerce").fillna(9999).astype(int)
        df["rank_key_not_ready"] = (~df["claim_ready_for_allatom"].astype(bool)).astype(int)
        df = df.sort_values(["rank_key_claim_failed", "rank_key_not_ready", "profile_tag"]).reset_index(drop=True)
    best_row = df.iloc[0].to_dict() if (not df.empty) else {}
    overall_pass = bool((not df.empty) and bool(df.iloc[0]["pass"]))

    summary = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "profiles_requested_max": int(args.max_profiles),
        "profiles_executed": int(len(rows)),
        "targets": str(args.targets),
        "resolved_inputs": {
            "manifest_csv": manifest_csv,
            "strict_summary_json": strict_summary_json,
            "accuracy_external_csv": accuracy_external_csv,
            "policy_json": policy_json,
        },
        "overall_pass": bool(overall_pass),
        "best_profile_tag": str(best_row.get("profile_tag", "")),
        "best_claim_ready_for_allatom": bool(best_row.get("claim_ready_for_allatom", False)),
        "best_claim_failed_metrics": _safe_int(best_row.get("claim_failed_metrics", -1), default=-1),
        "best_failed_claim_metrics": _safe_str(best_row.get("failed_claim_metrics", "")),
        "artifacts": {
            "results_csv": f"{args.out_prefix}_results.csv",
            "summary_json": f"{args.out_prefix}_summary.json",
            "summary_md": f"{args.out_prefix}_summary.md",
            "commands_json": f"{args.out_prefix}_commands.json",
        },
    }

    results_csv = f"{args.out_prefix}_results.csv"
    summary_json = f"{args.out_prefix}_summary.json"
    summary_md = f"{args.out_prefix}_summary.md"
    commands_json = f"{args.out_prefix}_commands.json"
    df.to_csv(results_csv, index=False)
    with open(summary_json, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "rows": rows}, f, indent=2, ensure_ascii=False)
    with open(commands_json, "w", encoding="utf-8") as f:
        json.dump(command_logs, f, indent=2, ensure_ascii=False)

    lines = [
        "# Claim Input Profile Sweep",
        "",
        f"- profiles_executed: {summary['profiles_executed']}",
        f"- overall_pass: {summary['overall_pass']}",
        f"- best_profile_tag: {summary['best_profile_tag']}",
        f"- best_claim_ready_for_allatom: {summary['best_claim_ready_for_allatom']}",
        f"- best_claim_failed_metrics: {summary['best_claim_failed_metrics']}",
        f"- best_failed_claim_metrics: {summary['best_failed_claim_metrics']}",
        "",
        "## Top Profiles",
    ]
    for _, row in df.head(10).iterrows():
        lines.append(
            f"- {row.get('profile_tag')} pass={row.get('pass')} "
            f"claim_ready={row.get('claim_ready_for_allatom')} "
            f"failed={row.get('claim_failed_metrics')} "
            f"metrics={row.get('failed_claim_metrics')}"
        )
    with open(summary_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return {"summary": summary, "rows": rows, "command_logs": command_logs}


def build_parser() -> argparse.ArgumentParser:
    stamp = dt.date.today().isoformat()
    p = argparse.ArgumentParser(
        description=(
            "Sweep robust claim-input estimator profiles and rank by initial all-atom claim readiness "
            "without correction loop."
        )
    )
    p.add_argument("--manifest-csv", type=str, required=True)
    p.add_argument("--targets", type=str, default="all")
    p.add_argument("--policy-json", type=str, default="config/allatom_equivalence_acceptance_v1_2026-02-17.json")
    p.add_argument("--strict-summary-json", type=str, required=True)
    p.add_argument("--accuracy-external-csv", type=str, required=True)
    p.add_argument("--expected-target-count", type=int, default=10)
    p.add_argument("--split-modes", type=str, default="window_stratified,half")
    p.add_argument("--split-replicas-list", type=str, default="3,5")
    p.add_argument("--split-window-frames-list", type=str, default="24")
    p.add_argument("--split-window-stride-list", type=str, default="12")
    p.add_argument("--min-effective-frames-list", type=str, default="8")
    p.add_argument("--thermo-agg-methods", type=str, default="median,trimmed")
    p.add_argument("--kinetics-agg-methods", type=str, default="trimmed,median")
    p.add_argument("--experiment-agg-methods", type=str, default="median")
    p.add_argument("--trim-fractions", type=str, default="0.10,0.15")
    p.add_argument("--tail-clip-pairs", type=str, default="0.01:0.99,0.02:0.98")
    p.add_argument("--pmf-pseudocounts", type=str, default="1e-4,1e-3,1e-2,1e-1,0.5,1.0")
    p.add_argument("--kinetics-min-signal-stds", type=str, default="1e-6")
    p.add_argument("--kinetics-min-denom-epss", type=str, default="1e-12")
    p.add_argument("--max-profiles", type=int, default=48)
    p.add_argument("--enforce-complete-claim", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--force-rust", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--fail-fast", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--out-prefix", type=str, default=f"runs/claim_input_profile_sweep_{stamp}")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = run_sweep(args)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))
    print(f"Wrote CSV: {args.out_prefix}_results.csv")
    print(f"Wrote JSON: {args.out_prefix}_summary.json")
    print(f"Wrote MD: {args.out_prefix}_summary.md")
    print(f"Wrote command log: {args.out_prefix}_commands.json")
    if not bool(payload["summary"].get("overall_pass", False)):
        sys.exit(2)


if __name__ == "__main__":
    main()
