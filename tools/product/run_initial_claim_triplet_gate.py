#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

from tools.speed_profile_defaults import load_speed_profile_section, resolve_speed_profile


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
        if isinstance(payload, dict):
            return payload
        return {}
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


def _apply_claim_profile_json(args: argparse.Namespace) -> Dict[str, Any]:
    profile_path = _resolve_input_path(str(getattr(args, "claim_profile_json", "")).strip())
    payload = _read_json(profile_path)
    if not payload:
        return {"path": profile_path, "loaded": False, "keys_applied": []}
    profile = payload.get("profile", payload) if isinstance(payload, dict) else {}
    if not isinstance(profile, dict):
        return {"path": profile_path, "loaded": False, "keys_applied": []}

    field_casts = {
        "claim_split_mode": str,
        "claim_split_replicas": int,
        "claim_split_window_frames": int,
        "claim_split_window_stride": int,
        "claim_min_effective_frames": int,
        "claim_thermo_agg_method": str,
        "claim_kinetics_agg_method": str,
        "claim_experiment_agg_method": str,
        "claim_trim_fraction": float,
        "claim_tail_clip_low": float,
        "claim_tail_clip_high": float,
        "claim_pmf_pseudocount": float,
        "claim_kinetics_min_signal_std": float,
        "claim_kinetics_min_denom_eps": float,
    }
    keys_applied: List[str] = []
    for key, caster in field_casts.items():
        if key not in profile:
            continue
        try:
            setattr(args, key, caster(profile.get(key)))
            keys_applied.append(key)
        except Exception:
            continue
    return {"path": profile_path, "loaded": True, "keys_applied": keys_applied}


def _bool_flag(v: bool, true_opt: str, false_opt: str) -> str:
    return str(true_opt) if bool(v) else str(false_opt)


def _safe_int(v: Any, default: int = -1) -> int:
    try:
        if v is None:
            return int(default)
        return int(v)
    except Exception:
        return int(default)


def run_triplet(args: argparse.Namespace) -> Dict[str, Any]:
    claim_profile_status = _apply_claim_profile_json(args)
    speed_profile_defaults = load_speed_profile_section(
        str(getattr(args, "speed_profile_defaults_json", "")).strip(),
        str(getattr(args, "speed_profile_defaults_section", "initial_claim_triplet")).strip()
        or "initial_claim_triplet",
    )
    resolved_speed_profile = resolve_speed_profile(
        explicit_mode=getattr(args, "speed_mode", ""),
        explicit_replicas=getattr(args, "speed_mode_replicas", -1),
        explicit_max_replicas=getattr(args, "speed_profile_max_replicas", -1),
        section_defaults=speed_profile_defaults,
        fallback={
            "speed_mode": "max",
            "speed_mode_replicas": 128,
            "speed_profile_max_replicas": 128,
        },
    )
    args.speed_mode = str(resolved_speed_profile.get("speed_mode", "max"))
    args.speed_mode_replicas = int(resolved_speed_profile.get("speed_mode_replicas", 128))
    args.speed_profile_max_replicas = int(
        resolved_speed_profile.get("speed_profile_max_replicas", 128)
    )
    repeats = max(1, int(args.repeats))
    date_tag_base = str(args.date_tag).strip() or dt.date.today().isoformat()
    runs_dir = str(args.runs_dir).strip()
    os.makedirs(runs_dir, exist_ok=True)

    env = os.environ.copy()
    if bool(args.force_rust):
        env["FORCE_RUST_HIP"] = "1"
        env["RUST_HIP_USE_GPU_NBLIST_BUILDER"] = "1"

    rows: List[Dict[str, Any]] = []
    command_logs: List[Dict[str, Any]] = []
    first_failed_replicate: Optional[int] = None

    for i in range(1, repeats + 1):
        rep_tag = f"{date_tag_base}_rep{i}"
        nightly_cmd: List[str] = [
            sys.executable,
            "tools/run_nightly_screening_batch.py",
            "--date-tag",
            rep_tag,
            "--mode",
            str(args.mode),
            "--targets",
            str(args.targets),
            "--runs-dir",
            runs_dir,
            "--public-out-dir",
            str(args.public_out_dir),
            "--sources-csv",
            str(args.sources_csv),
            "--external-manifest",
            str(args.external_manifest),
            "--strict-summary-json",
            str(args.strict_summary_json),
            "--accuracy-external-csv",
            str(args.accuracy_external_csv),
            "--claim-policy-json",
            str(args.claim_policy_json),
            "--long-stability-gate-policy",
            str(args.long_stability_gate_policy),
            "--speed-mode",
            str(args.speed_mode),
            "--speed-mode-replicas",
            str(int(args.speed_mode_replicas)),
            "--speed-profile-max-replicas",
            str(int(args.speed_profile_max_replicas)),
            "--claim-split-mode",
            str(args.claim_split_mode),
            "--claim-split-replicas",
            str(int(args.claim_split_replicas)),
            "--claim-split-window-frames",
            str(int(args.claim_split_window_frames)),
            "--claim-split-window-stride",
            str(int(args.claim_split_window_stride)),
            "--claim-min-effective-frames",
            str(int(args.claim_min_effective_frames)),
            "--claim-thermo-agg-method",
            str(args.claim_thermo_agg_method),
            "--claim-kinetics-agg-method",
            str(args.claim_kinetics_agg_method),
            "--claim-experiment-agg-method",
            str(args.claim_experiment_agg_method),
            "--claim-trim-fraction",
            str(float(args.claim_trim_fraction)),
            "--claim-tail-clip-low",
            str(float(args.claim_tail_clip_low)),
            "--claim-tail-clip-high",
            str(float(args.claim_tail_clip_high)),
            "--claim-pmf-pseudocount",
            str(float(args.claim_pmf_pseudocount)),
            "--claim-kinetics-min-signal-std",
            str(float(args.claim_kinetics_min_signal_std)),
            "--claim-kinetics-min-denom-eps",
            str(float(args.claim_kinetics_min_denom_eps)),
            _bool_flag(bool(args.run_ood_gate), "--run-ood-gate", "--no-run-ood-gate"),
            _bool_flag(bool(args.run_ood_measured20), "--run-ood-measured20", "--no-run-ood-measured20"),
            _bool_flag(bool(args.run_claim_correction), "--run-claim-correction", "--no-run-claim-correction"),
            _bool_flag(bool(args.run_special_cases), "--run-special-cases", "--no-run-special-cases"),
            _bool_flag(bool(args.claim_require_initial_ready), "--claim-require-initial-ready", "--no-claim-require-initial-ready"),
            _bool_flag(bool(args.fail_fast_nightly), "--fail-fast", "--no-fail-fast"),
        ]
        if bool(args.run_ood_measured20):
            nightly_cmd.extend(
                [
                    "--ood-measured20-sources-csv",
                    str(args.ood_measured20_sources_csv),
                    "--ood-measured20-tags-csv",
                    str(args.ood_measured20_tags_csv),
                    "--ood-measured20-min-pairs",
                    str(int(args.ood_measured20_min_pairs)),
                    "--ood-measured20-max-mean-rmsd",
                    str(float(args.ood_measured20_max_mean_rmsd)),
                ]
            )
            if int(args.ood_measured20_min_domain_coverage) > 0:
                nightly_cmd.extend(
                    [
                        "--ood-measured20-min-domain-coverage",
                        str(int(args.ood_measured20_min_domain_coverage)),
                    ]
                )
        if bool(args.dry_run):
            nightly_cmd.append("--dry-run")

        rec = _run_cmd(nightly_cmd, env=env, dry_run=bool(args.dry_run))
        rec["replicate"] = int(i)
        command_logs.append(rec)

        summary_json = os.path.join(runs_dir, f"nightly_screening_batch_{rep_tag}.json")
        payload = _read_json(summary_json) if (not bool(args.dry_run)) else {}
        claim_status = payload.get("claim_status", {}) if isinstance(payload.get("claim_status"), dict) else {}
        nightly_pass = bool(payload.get("pass", False)) if payload else bool(rec.get("ok", False))
        initial_ready = claim_status.get("initial_claim_ready_for_allatom", None)
        initial_failed_metrics = claim_status.get("initial_claim_failed_metrics", None)
        initial_failed_i = _safe_int(initial_failed_metrics, default=-1)
        if bool(args.dry_run):
            rep_pass = bool(rec.get("ok", False))
        else:
            rep_pass = bool(nightly_pass and (initial_ready is True) and (initial_failed_i == 0))

        reasons: List[str] = []
        if not bool(rec.get("ok", False)):
            reasons.append("nightly_command_failed")
        if payload and (not nightly_pass):
            reasons.append("nightly_summary_pass_false")
        if (not bool(args.dry_run)) and (initial_ready is not True):
            reasons.append("initial_claim_not_ready")
        if (not bool(args.dry_run)) and (initial_failed_i != 0):
            reasons.append("initial_claim_failed_metrics_nonzero")

        rows.append(
            {
                "replicate": int(i),
                "date_tag": rep_tag,
                "nightly_command_ok": bool(rec.get("ok", False)),
                "nightly_summary_pass": bool(nightly_pass),
                "initial_claim_ready_for_allatom": initial_ready,
                "initial_claim_failed_metrics": initial_failed_metrics,
                "rep_pass": bool(rep_pass),
                "reason": ";".join(reasons),
                "nightly_summary_json": summary_json,
            }
        )

        if (not rep_pass) and bool(args.fail_fast):
            first_failed_replicate = int(i)
            break

    df = pd.DataFrame(rows)
    all_pass = bool((len(rows) >= repeats) and (not df.empty) and bool(df["rep_pass"].all()))
    summary = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "repeats_requested": int(repeats),
        "repeats_executed": int(len(rows)),
        "mode": str(args.mode),
        "targets": str(args.targets),
        "claim_require_initial_ready": bool(args.claim_require_initial_ready),
        "run_claim_correction": bool(args.run_claim_correction),
        "run_ood_gate": bool(args.run_ood_gate),
        "run_ood_measured20": bool(args.run_ood_measured20),
        "run_special_cases": bool(args.run_special_cases),
        "claim_profile": claim_profile_status,
        "speed_profile_defaults": {
            "json": str(getattr(args, "speed_profile_defaults_json", "")).strip(),
            "section": str(
                getattr(args, "speed_profile_defaults_section", "initial_claim_triplet")
            ).strip()
            or "initial_claim_triplet",
            "resolved": resolved_speed_profile,
        },
        "pass": bool(all_pass),
        "first_failed_replicate": first_failed_replicate,
    }

    os.makedirs(os.path.dirname(str(args.out_csv)) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(str(args.out_json)) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(str(args.out_md)) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(str(args.out_commands_json)) or ".", exist_ok=True)
    df.to_csv(str(args.out_csv), index=False)
    with open(str(args.out_json), "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "rows": rows}, f, indent=2, ensure_ascii=False)
    with open(str(args.out_commands_json), "w", encoding="utf-8") as f:
        json.dump(command_logs, f, indent=2, ensure_ascii=False)

    lines = [
        "# Initial Claim Triplet Gate",
        "",
        f"- repeats_requested: {summary['repeats_requested']}",
        f"- repeats_executed: {summary['repeats_executed']}",
        f"- mode: {summary['mode']}",
        f"- targets: {summary['targets']}",
        f"- pass: {summary['pass']}",
        f"- first_failed_replicate: {summary['first_failed_replicate']}",
        f"- claim_profile_json: {claim_profile_status.get('path')}",
        f"- claim_profile_loaded: {claim_profile_status.get('loaded')}",
        f"- claim_profile_keys_applied: {claim_profile_status.get('keys_applied')}",
        f"- speed_profile_defaults_json: {str(getattr(args, 'speed_profile_defaults_json', '')).strip()}",
        f"- speed_profile_defaults_section: "
        f"{str(getattr(args, 'speed_profile_defaults_section', 'initial_claim_triplet')).strip() or 'initial_claim_triplet'}",
        f"- resolved_speed_profile: {resolved_speed_profile}",
        "",
        "## Replicates",
    ]
    for row in rows:
        lines.append(
            f"- rep={row['replicate']} pass={row['rep_pass']} "
            f"initial_ready={row['initial_claim_ready_for_allatom']} "
            f"failed_metrics={row['initial_claim_failed_metrics']} "
            f"reason={row['reason']}"
        )
    with open(str(args.out_md), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return {"summary": summary, "rows": rows, "command_logs": command_logs}


def build_parser() -> argparse.ArgumentParser:
    stamp = dt.date.today().isoformat()
    p = argparse.ArgumentParser(
        description=(
            "Run nightly batch multiple times and require initial claim readiness PASS "
            "consecutively (default: 3)."
        )
    )
    p.add_argument("--date-tag", type=str, default="")
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--mode", type=str, default="full", choices=["smoke", "full"])
    p.add_argument("--targets", type=str, default="all")
    p.add_argument("--runs-dir", type=str, default="runs")
    p.add_argument("--public-out-dir", type=str, default="data/public_structures/nightly")
    p.add_argument("--sources-csv", type=str, default="config/structure_sources_10targets.csv")
    p.add_argument("--external-manifest", type=str, default="runs/real_md_source_manifest_openmm_2bead_2026-02-17.csv")
    p.add_argument("--strict-summary-json", type=str, default="runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_summary.json")
    p.add_argument("--accuracy-external-csv", type=str, default="runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_accuracy_external.csv")
    p.add_argument("--claim-policy-json", type=str, default="config/allatom_equivalence_acceptance_v1_2026-02-17.json")
    p.add_argument("--claim-profile-json", type=str, default="config/claim_input_profile_accuracy_v1_2026-02-19.json")
    p.add_argument("--long-stability-gate-policy", type=str, default="strict", choices=["strict", "pragmatic"])
    p.add_argument("--run-ood-gate", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--run-ood-measured20", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--ood-measured20-sources-csv", type=str, default="config/structure_sources_ood_measured20_v1.csv")
    p.add_argument("--ood-measured20-tags-csv", type=str, default="config/structure_sources_ood_measured20_tags_v1.csv")
    p.add_argument("--ood-measured20-min-pairs", type=int, default=16)
    p.add_argument("--ood-measured20-max-mean-rmsd", type=float, default=6.0)
    p.add_argument("--ood-measured20-min-domain-coverage", type=int, default=0)
    p.add_argument("--run-claim-correction", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--run-special-cases", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--claim-require-initial-ready", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--speed-profile-defaults-json", type=str, default="config/speed_profile_defaults.json")
    p.add_argument("--speed-profile-defaults-section", type=str, default="initial_claim_triplet")
    p.add_argument("--speed-mode", type=str, default="")
    p.add_argument("--speed-mode-replicas", type=int, default=-1)
    p.add_argument("--speed-profile-max-replicas", type=int, default=-1)
    p.add_argument("--claim-split-mode", type=str, choices=["window_stratified", "half"], default="window_stratified")
    p.add_argument("--claim-split-replicas", type=int, default=5)
    p.add_argument("--claim-split-window-frames", type=int, default=24)
    p.add_argument("--claim-split-window-stride", type=int, default=12)
    p.add_argument("--claim-min-effective-frames", type=int, default=8)
    p.add_argument("--claim-thermo-agg-method", type=str, choices=["mean", "median", "trimmed"], default="median")
    p.add_argument("--claim-kinetics-agg-method", type=str, choices=["mean", "median", "trimmed"], default="trimmed")
    p.add_argument("--claim-experiment-agg-method", type=str, choices=["mean", "median", "trimmed"], default="median")
    p.add_argument("--claim-trim-fraction", type=float, default=0.10)
    p.add_argument("--claim-tail-clip-low", type=float, default=0.01)
    p.add_argument("--claim-tail-clip-high", type=float, default=0.99)
    p.add_argument("--claim-pmf-pseudocount", type=float, default=1.0)
    p.add_argument("--claim-kinetics-min-signal-std", type=float, default=1e-6)
    p.add_argument("--claim-kinetics-min-denom-eps", type=float, default=1e-12)
    p.add_argument("--force-rust", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--fail-fast-nightly", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--fail-fast", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--out-csv", type=str, default=f"runs/initial_claim_triplet_gate_{stamp}.csv")
    p.add_argument("--out-json", type=str, default=f"runs/initial_claim_triplet_gate_{stamp}.json")
    p.add_argument("--out-md", type=str, default=f"runs/initial_claim_triplet_gate_{stamp}.md")
    p.add_argument("--out-commands-json", type=str, default=f"runs/initial_claim_triplet_gate_{stamp}_commands.json")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = run_triplet(args)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))
    print(f"Wrote CSV: {args.out_csv}")
    print(f"Wrote JSON: {args.out_json}")
    print(f"Wrote MD: {args.out_md}")
    print(f"Wrote command log: {args.out_commands_json}")
    if not bool(payload["summary"].get("pass", False)):
        sys.exit(2)


if __name__ == "__main__":
    main()
