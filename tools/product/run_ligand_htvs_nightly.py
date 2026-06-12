#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Sequence


def _read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if not isinstance(obj, dict):
        raise ValueError(f"profile must be JSON object: {path}")
    return obj


def _ensure_parent(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


def _run(cmd: List[str], env: Dict[str, str]) -> Dict[str, Any]:
    p = subprocess.run(cmd, text=True, capture_output=True, env=env)
    return {
        "cmd": cmd,
        "cmd_str": " ".join(cmd),
        "ok": bool(p.returncode == 0),
        "returncode": int(p.returncode),
        "stdout_tail": "\n".join((p.stdout or "").splitlines()[-80:]),
        "stderr_tail": "\n".join((p.stderr or "").splitlines()[-80:]),
    }


def _safe_copy(src: str, dst: str) -> bool:
    if (not src) or (not os.path.exists(src)):
        return False
    _ensure_parent(dst)
    shutil.copy2(src, dst)
    return True


def run_nightly(args: argparse.Namespace) -> Dict[str, Any]:
    profile_json = str(args.profile_json).strip()
    if (not profile_json) or (not os.path.exists(profile_json)):
        raise FileNotFoundError(f"profile json not found: {profile_json}")
    prof = _read_json(profile_json)

    date_tag = str(args.date_tag).strip() or dt.date.today().isoformat()
    out_prefix = str(args.out_prefix).strip() or f"runs/ligand_htvs_nightly_{date_tag}"
    summary_json = f"{out_prefix}_summary.json"
    summary_md = f"{out_prefix}_summary.md"
    status_json = f"{out_prefix}_status.json"
    status_md = f"{out_prefix}_status.md"
    _ensure_parent(status_json)

    smoke = prof.get("smoke", {}) if isinstance(prof.get("smoke"), dict) else {}
    full = prof.get("full", {}) if isinstance(prof.get("full"), dict) else {}
    gate = prof.get("gate", {}) if isinstance(prof.get("gate"), dict) else {}
    retry = prof.get("retry", {}) if isinstance(prof.get("retry"), dict) else {}

    calib_ref_csv = str(prof.get("calibration_reference_csv", "config/ligand_binding_reference_expanded_v2.csv"))
    ranking_labels_csv = str(prof.get("ranking_labels_csv", "config/ligand_binding_reference_expanded_v2.csv"))
    eval_split_csv = str(prof.get("eval_split_csv", ""))
    ligand_csv_effective = str(prof.get("ligand_csv", "config/ligand_smoke_seed_v1.csv"))

    pre_stage: Dict[str, Any] = {"ok": True, "skipped": True, "cmd": [], "cmd_str": ""}
    if bool(prof.get("build_hard_decoy_benchmark", False)):
        hard_labels = f"{out_prefix}_hard_decoy_labels.csv"
        hard_split = f"{out_prefix}_hard_decoy_split.csv"
        pre_cmd = [
            sys.executable,
            "tools/build_hard_decoy_benchmark.py",
            "--reference-csv",
            str(prof.get("hard_decoy_reference_csv", ranking_labels_csv)),
            "--targets",
            str(prof.get("hard_decoy_targets", str(args.targets or prof.get("targets", "KRAS_G12D,EGFR_KINASE,HIV1_PROTEASE")))),
            "--ligand-meta-csv",
            str(prof.get("hard_decoy_ligand_meta_csv", "")),
            "--target-meta-csv",
            str(prof.get("hard_decoy_target_meta_csv", "")),
            "--fit-targets",
            str(prof.get("hard_decoy_fit_targets", "")),
            "--hard-decoy-quantile",
            str(float(prof.get("hard_decoy_quantile", 0.5))),
            "--min-hard-decoys-per-target",
            str(int(prof.get("hard_decoy_min_per_target", 1))),
            "--max-hard-decoys-per-target",
            str(int(prof.get("hard_decoy_max_per_target", 0))),
            "--synthesize-unique-decoys"
            if bool(prof.get("hard_decoy_synthesize_unique_decoys", False))
            else "--no-synthesize-unique-decoys",
            "--synth-total-decoys",
            str(int(prof.get("hard_decoy_synth_total_decoys", 0))),
            "--synth-decoys-per-target",
            str(int(prof.get("hard_decoy_synth_decoys_per_target", 0))),
            "--synth-random-seed",
            str(int(prof.get("hard_decoy_synth_random_seed", 13))),
            "--synth-max-attempt-mult",
            str(int(prof.get("hard_decoy_synth_max_attempt_mult", 400))),
            "--synth-keep-all-decoys"
            if bool(prof.get("hard_decoy_synth_keep_all_decoys", True))
            else "--no-synth-keep-all-decoys",
            "--synth-allow-shortfall"
            if bool(prof.get("hard_decoy_synth_allow_shortfall", False))
            else "--no-synth-allow-shortfall",
            "--out-labels-csv",
            hard_labels,
            "--out-split-csv",
            hard_split,
            "--out-json",
            f"{out_prefix}_hard_decoy_summary.json",
            "--out-md",
            f"{out_prefix}_hard_decoy_summary.md",
        ]
        pre_stage = _run(pre_cmd, env=dict(os.environ))
        if not bool(pre_stage.get("ok", False)):
            payload = {
                "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
                "profile_json": profile_json,
                "pass": False,
                "failed_stage": "pre_hard_decoy_benchmark",
                "command": pre_stage,
                "attempts": [],
                "artifacts": {
                    "pipeline_summary_json": summary_json,
                    "pipeline_summary_md": summary_md,
                    "status_json": status_json,
                    "status_md": status_md,
                },
            }
            with open(status_json, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            return payload
        calib_ref_csv = hard_labels
        ranking_labels_csv = hard_labels
        eval_split_csv = hard_split
        ligand_csv_effective = hard_labels

    cmd = [
        sys.executable,
        "tools/run_ligand_htvs_pipeline.py",
        "--run-scope",
        str(args.run_scope or prof.get("run_scope", "smoke_then_full")),
        "--targets",
        str(args.targets or prof.get("targets", "KRAS_G12D,EGFR_KINASE,HIV1_PROTEASE")),
        "--out-prefix",
        out_prefix,
        "--ligand-csv",
        str(ligand_csv_effective),
        "--trajectory-engine-mode",
        str(prof.get("trajectory_engine_mode", "rust_hip")),
        "--stage3-min-frames",
        str(int(prof.get("stage3_min_frames", 100))),
        "--stage3-workers",
        str(int(prof.get("stage3_workers", 0))),
        "--stage3-parallel-threshold",
        str(int(prof.get("stage3_parallel_threshold", 2))),
        "--stage3-score-only" if bool(prof.get("stage3_score_only", True)) else "--no-stage3-score-only",
        "--emit-sla-summary" if bool(prof.get("emit_sla_summary", True)) else "--no-emit-sla-summary",
        "--make-bundle-zip" if bool(prof.get("make_bundle_zip", True)) else "--no-make-bundle-zip",
        "--traj-auto-fast-output"
        if bool(prof.get("traj_auto_fast_output", True))
        else "--no-traj-auto-fast-output",
        "--calibration-reference-csv",
        str(calib_ref_csv),
        "--eval-split-csv",
        str(eval_split_csv),
        "--calibration-fit-roles",
        str(prof.get("calibration_fit_roles", "fit")),
        "--require-split-for-calibration" if bool(prof.get("require_split_for_calibration", False)) else "--no-require-split-for-calibration",
        "--ranking-labels-csv",
        str(ranking_labels_csv),
        "--ranking-eval-roles",
        str(prof.get("ranking_eval_roles", "eval")),
        "--ranking-ood-eval-roles",
        str(prof.get("ranking_ood_eval_roles", "ood_eval")),
        "--run-calibration" if bool(prof.get("run_calibration", True)) else "--no-run-calibration",
        "--run-ranking-eval" if bool(prof.get("run_ranking_eval", True)) else "--no-run-ranking-eval",
        "--require-split-for-ranking" if bool(prof.get("require_split_for_ranking", False)) else "--no-require-split-for-ranking",
        "--require-ood-eval" if bool(prof.get("require_ood_eval", False)) else "--no-require-ood-eval",
        "--enforce-zero-overlap" if bool(prof.get("enforce_zero_overlap", False)) else "--no-enforce-zero-overlap",
        "--run-leakage-audit" if bool(prof.get("run_leakage_audit", False)) else "--no-run-leakage-audit",
        "--leakage-fit-roles",
        str(prof.get("leakage_fit_roles", "fit")),
        "--leakage-eval-roles",
        str(prof.get("leakage_eval_roles", "")),
        "--leakage-target-meta-csv",
        str(prof.get("leakage_target_meta_csv", "")),
        "--leakage-ligand-meta-csv",
        str(prof.get("leakage_ligand_meta_csv", "")),
        "--leakage-max-key-overlap",
        str(int(prof.get("leakage_max_key_overlap", 0))),
        "--leakage-max-target-overlap",
        str(int(prof.get("leakage_max_target_overlap", 0))),
        "--leakage-max-family-overlap-ratio",
        str(float(prof.get("leakage_max_family_overlap_ratio", 0.0))),
        "--leakage-max-scaffold-overlap-ratio",
        str(float(prof.get("leakage_max_scaffold_overlap_ratio", 0.0))),
        "--leakage-max-allowed-seq-identity",
        str(float(prof.get("leakage_max_allowed_seq_identity", 0.30))),
        "--leakage-max-allowed-pocket-jaccard",
        str(float(prof.get("leakage_max_allowed_pocket_jaccard", 0.40))),
        "--gate-min-frames",
        str(int(gate.get("min_frames", 100))),
        "--gate-max-mean-min-distance-A",
        str(float(gate.get("max_mean_min_distance_A", 2.5))),
        "--gate-ranking-auc-min",
        str(float(gate.get("ranking_auc_min", 0.9))),
        "--gate-ranking-unique-auc-min",
        str(float(gate.get("ranking_unique_auc_min", gate.get("ranking_auc_min", 0.9)))),
        "--gate-ranking-ood-auc-min",
        str(float(gate.get("ranking_ood_auc_min", 0.85))),
        "--gate-pr-auc-min",
        str(float(gate.get("pr_auc_min", 0.60))),
        "--gate-ef1-min",
        str(float(gate.get("ef1_min", 1.25))),
        "--gate-bedroc-min",
        str(float(gate.get("bedroc_min", 0.30))),
        "--gate-brier-max",
        str(float(gate.get("brier_max", 0.30))),
        "--gate-ece-max",
        str(float(gate.get("ece_max", 0.30))),
        "--gate-roc-auc-ci-lower-min",
        str(float(gate.get("roc_auc_ci_lower_min", 0.80))),
        "--gate-pr-auc-ci-lower-min",
        str(float(gate.get("pr_auc_ci_lower_min", 0.50))),
        "--gate-ef1-ci-lower-min",
        str(float(gate.get("ef1_ci_lower_min", 1.00))),
        "--gate-topk-k",
        str(int(gate.get("topk_k", 10))),
        "--gate-topk-hit-rate-min",
        str(float(gate.get("topk_hit_rate_min", 0.8))),
        "--ranking-bootstrap-n",
        str(int(prof.get("ranking_bootstrap_n", 400))),
        "--ranking-bootstrap-seed",
        str(int(prof.get("ranking_bootstrap_seed", 7))),
        "--ranking-bootstrap-bedroc-alpha",
        str(float(prof.get("ranking_bootstrap_bedroc_alpha", 20.0))),
        "--ranking-ece-bins",
        str(int(prof.get("ranking_ece_bins", 10))),
        "--ranking-probability-logit-scale",
        str(float(prof.get("ranking_probability_logit_scale", 1.35))),
        "--replicas-smoke",
        str(int(smoke.get("replicas", 24))),
        "--max-ligands-smoke",
        str(int(smoke.get("max_ligands", 24))),
        "--jobs-per-target-smoke",
        str(int(smoke.get("jobs_per_target", 24))),
        "--traj-frames-smoke",
        str(int(smoke.get("traj_frames", 80))),
        "--max-jobs-score-smoke",
        str(int(smoke.get("max_jobs_score", 96))),
        "--replicas-full",
        str(int(full.get("replicas", 64))),
        "--max-ligands-full",
        str(int(full.get("max_ligands", 64))),
        "--jobs-per-target-full",
        str(int(full.get("jobs_per_target", 64))),
        "--traj-frames-full",
        str(int(full.get("traj_frames", 120))),
        "--max-jobs-score-full",
        str(int(full.get("max_jobs_score", 640))),
        "--traj-dynamic-core-fallback-on-oom"
        if bool(prof.get("traj_dynamic_core_fallback_on_oom", False))
        else "--no-traj-dynamic-core-fallback-on-oom",
        "--traj-abort-on-runtime-error"
        if bool(prof.get("traj_abort_on_runtime_error", True))
        else "--no-traj-abort-on-runtime-error",
        "--traj-abort-on-cpu-backend"
        if bool(prof.get("traj_abort_on_cpu_backend", True))
        else "--no-traj-abort-on-cpu-backend",
        "--traj-frame-output-format",
        str(prof.get("traj_frame_output_format", "pdb_files")),
        "--traj-npz-compression",
        str(prof.get("traj_npz_compression", "store")),
        "--traj-npz-layout",
        str(prof.get("traj_npz_layout", "flat_shard")),
        "--traj-npz-shard-size",
        str(int(prof.get("traj_npz_shard_size", 512))),
        "--traj-job-batch-autotune-candidates",
        str(prof.get("traj_job_batch_autotune_candidates", "1,2,4,8")),
        "--traj-job-batch-autotune-frames",
        str(int(prof.get("traj_job_batch_autotune_frames", 12))),
        "--traj-writer-workers",
        str(int(prof.get("traj_writer_workers", 1))),
        "--traj-writer-mode",
        str(prof.get("traj_writer_mode", "process")),
        "--traj-writer-max-pending",
        str(int(prof.get("traj_writer_max_pending", 64))),
        "--traj-prod-speedpack" if bool(prof.get("traj_prod_speedpack", False)) else "--no-traj-prod-speedpack",
        "--traj-prod-adaptive-frame-budget"
        if bool(prof.get("traj_prod_adaptive_frame_budget", True))
        else "--no-traj-prod-adaptive-frame-budget",
        "--traj-prod-frame-budget-tiers",
        str(prof.get("traj_prod_frame_budget_tiers", "0.90:1.00,0.75:0.85,0.60:0.70,0.00:0.55")),
        "--traj-prod-min-frames-smoke",
        str(int(prof.get("traj_prod_min_frames_smoke", 80))),
        "--traj-prod-min-frames-full",
        str(int(prof.get("traj_prod_min_frames_full", 160))),
        "--traj-prod-early-stop-enabled"
        if bool(prof.get("traj_prod_early_stop_enabled", False))
        else "--no-traj-prod-early-stop-enabled",
        "--traj-prod-early-stop-min-frames-smoke",
        str(int(prof.get("traj_prod_early_stop_min_frames_smoke", 80))),
        "--traj-prod-early-stop-min-frames-full",
        str(int(prof.get("traj_prod_early_stop_min_frames_full", 160))),
        "--traj-prod-early-stop-window",
        str(int(prof.get("traj_prod_early_stop_window", 12))),
        "--traj-prod-early-stop-contact-drift",
        str(float(prof.get("traj_prod_early_stop_contact_drift", 0.015))),
        "--traj-prod-early-stop-min-distance-drift-A",
        str(float(prof.get("traj_prod_early_stop_min_distance_drift_A", 0.12))),
        "--traj-prod-early-stop-max-mean-min-distance-A",
        str(float(prof.get("traj_prod_early_stop_max_mean_min_distance_A", 6.0))),
        "--traj-dynamic-adress-min-affinity",
        str(float(prof.get("traj_dynamic_adress_min_affinity", 0.78))),
        "--traj-dynamic-adress-max-protein-residues",
        str(int(prof.get("traj_dynamic_adress_max_protein_residues", 200))),
        "--traj-dynamic-adress-min-ligand-mw",
        str(float(prof.get("traj_dynamic_adress_min_ligand_mw", 250.0))),
        "--traj-dynamic-adress-fraction",
        str(float(prof.get("traj_dynamic_adress_fraction", 0.15))),
        "--traj-dynamic-adress-base-radius-A",
        str(float(prof.get("traj_dynamic_adress_base_radius_A", 6.0))),
        "--traj-dynamic-adress-affinity-radius-scale",
        str(float(prof.get("traj_dynamic_adress_affinity_radius_scale", 3.0))),
        "--traj-dynamic-adress-mw-radius-scale",
        str(float(prof.get("traj_dynamic_adress_mw_radius_scale", 2.5))),
        "--traj-dynamic-adress-max-all-atom-radius-A",
        str(float(prof.get("traj_dynamic_adress_max_all_atom_radius_A", 8.0))),
        "--traj-dynamic-adress-max-atom-ratio",
        str(float(prof.get("traj_dynamic_adress_max_atom_ratio", 0.10))),
        "--traj-dynamic-adress-cap-force-core-on-radius"
        if bool(prof.get("traj_dynamic_adress_cap_force_core_on_radius", True))
        else "--no-traj-dynamic-adress-cap-force-core-on-radius",
        "--strict-fail-fast" if bool(gate.get("strict_fail_fast", True)) else "--no-strict-fail-fast",
        "--enforce-operational-gate" if bool(gate.get("enforce_operational_gate", True)) else "--no-enforce-operational-gate",
        "--traj-require-rust-hip" if bool(prof.get("require_rust_hip", True)) else "--no-traj-require-rust-hip",
        "--no-dry-run" if (not bool(args.dry_run)) and (not bool(prof.get("dry_run", False))) else "--dry-run",
    ]
    gate_distance_override_csv = str(prof.get("gate_distance_override_csv", "") or "").strip()
    if gate_distance_override_csv:
        cmd.extend(["--gate-distance-override-csv", gate_distance_override_csv])

    env = dict(os.environ)
    env["FORCE_RUST_HIP"] = "1" if bool(prof.get("require_rust_hip", True)) else "0"
    env["RUST_HIP_USE_GPU_NBLIST_BUILDER"] = "1"
    env["AI_ROUTER_ONNX_ALLOW_CPU"] = "0"
    env["MD_GPU_ONLY"] = "1"
    retry_max_cfg = int(retry.get("max_attempts", 1))
    retry_sleep_cfg = int(retry.get("sleep_sec", 20))
    retry_max = int(args.retry_max) if int(args.retry_max) > 0 else retry_max_cfg
    retry_sleep_sec = int(args.retry_sleep_sec) if int(args.retry_sleep_sec) >= 0 else retry_sleep_cfg
    retry_max = max(1, retry_max)
    retry_sleep_sec = max(0, retry_sleep_sec)

    attempts: List[Dict[str, Any]] = []
    rec: Dict[str, Any] = {}
    summary_payload: Dict[str, Any] = {}
    pass_flag = False
    passed_attempt: Optional[int] = None

    for attempt in range(1, retry_max + 1):
        t0 = time.time()
        rec = _run(cmd, env=env)
        duration_sec = float(time.time() - t0)
        summary_payload = {}
        if os.path.exists(summary_json):
            try:
                summary_payload = _read_json(summary_json)
            except Exception:
                summary_payload = {}
        attempt_pass = bool(rec.get("ok", False)) and bool(summary_payload.get("pass", False))
        attempt_summary_json = f"{out_prefix}_attempt{attempt}_summary.json"
        attempt_summary_md = f"{out_prefix}_attempt{attempt}_summary.md"
        copied_summary_json = _safe_copy(summary_json, attempt_summary_json)
        copied_summary_md = _safe_copy(summary_md, attempt_summary_md)
        attempt_rec = {
            "attempt": int(attempt),
            "pass": bool(attempt_pass),
            "duration_sec": duration_sec,
            "command": rec,
            "artifacts": {
                "attempt_summary_json": attempt_summary_json if copied_summary_json else "",
                "attempt_summary_md": attempt_summary_md if copied_summary_md else "",
            },
        }
        attempts.append(attempt_rec)
        if attempt_pass:
            pass_flag = True
            passed_attempt = int(attempt)
            break
        if attempt < retry_max and retry_sleep_sec > 0:
            time.sleep(retry_sleep_sec)

    payload = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "profile_json": profile_json,
        "pass": bool(pass_flag),
        "retry_max": int(retry_max),
        "retry_sleep_sec": int(retry_sleep_sec),
        "attempt_count": len(attempts),
        "passed_attempt": passed_attempt,
        "date_tag": date_tag,
        "run_scope": str(args.run_scope or prof.get("run_scope", "smoke_then_full")),
        "targets": str(args.targets or prof.get("targets", "")),
        "pre_stage": pre_stage,
        "effective_inputs": {
            "ligand_csv": ligand_csv_effective,
            "calibration_reference_csv": calib_ref_csv,
            "ranking_labels_csv": ranking_labels_csv,
            "eval_split_csv": eval_split_csv,
            "gate_distance_override_csv": gate_distance_override_csv,
        },
        "command": rec,
        "attempts": attempts,
        "artifacts": {
            "pipeline_summary_json": summary_json,
            "pipeline_summary_md": summary_md,
            "status_json": status_json,
            "status_md": status_md,
        },
    }
    with open(status_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    lines = [
        "# Ligand HTVS Nightly Status",
        "",
        f"- generated_at_local: {payload['generated_at_local']}",
        f"- pass: {payload['pass']}",
        f"- profile_json: `{profile_json}`",
        f"- date_tag: {date_tag}",
        f"- run_scope: {payload['run_scope']}",
        f"- pre_stage_ok: {bool((payload.get('pre_stage') or {}).get('ok', True))}",
        f"- ligand_csv_effective: `{ligand_csv_effective}`",
        f"- eval_split_csv_effective: `{eval_split_csv}`",
        f"- retry_max: {payload['retry_max']}",
        f"- attempt_count: {payload['attempt_count']}",
        f"- passed_attempt: {payload['passed_attempt']}",
        f"- pipeline_summary_json: `{summary_json}`",
        f"- returncode: {rec.get('returncode')}",
    ]
    with open(status_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return payload


def build_parser() -> argparse.ArgumentParser:
    stamp = dt.date.today().isoformat()
    p = argparse.ArgumentParser(description="Run strict nightly ligand HTVS pipeline (smoke->full).")
    p.add_argument("--date-tag", type=str, default=stamp)
    p.add_argument("--profile-json", type=str, default="config/ligand_htvs_nightly_strict_v1.json")
    p.add_argument("--run-scope", type=str, default="", choices=["", "smoke", "full", "smoke_then_full"])
    p.add_argument("--targets", type=str, default="")
    p.add_argument("--out-prefix", type=str, default="")
    p.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--retry-max", type=int, default=0, help="Override retry max attempts (>0).")
    p.add_argument("--retry-sleep-sec", type=int, default=-1, help="Override sleep seconds between retries (>=0).")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = run_nightly(args)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if not bool(payload.get("pass", False)):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
