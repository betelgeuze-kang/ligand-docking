#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd


GATE_SPEED_LADDER: List[Dict[str, Any]] = [
    {"speed_mode": "balanced", "speed_mode_replicas": 4, "speed_profile_max_replicas": 64},
    {"speed_mode": "fast", "speed_mode_replicas": 32, "speed_profile_max_replicas": 128},
    {"speed_mode": "turbo", "speed_mode_replicas": 64, "speed_profile_max_replicas": 256},
    {"speed_mode": "extreme", "speed_mode_replicas": 128, "speed_profile_max_replicas": 512},
    {"speed_mode": "max", "speed_mode_replicas": 256, "speed_profile_max_replicas": 1024},
]


def _now_iso() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _ensure_parent(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


def _cmd_str(cmd: List[str]) -> str:
    return " ".join(cmd)


def _read_json_if_exists(path: str) -> Dict[str, Any]:
    src = str(path).strip()
    if not src or (not os.path.exists(src)):
        return {}
    try:
        with open(src, "r", encoding="utf-8") as f:
            payload = json.load(f)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _write_gate_attempts_csv(path: str, attempts: List[Dict[str, Any]]) -> str:
    out_path = str(path).strip()
    if not out_path:
        return out_path
    _ensure_parent(out_path)
    fields = [
        "attempt_index",
        "pass",
        "returncode",
        "speed_mode",
        "speed_mode_replicas",
        "speed_profile_max_replicas",
        "reason",
        "gate_json",
        "gate_csv",
        "stage2_csv",
        "benchmark_csv",
    ]
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for a in attempts:
            profile = a.get("profile", {}) if isinstance(a.get("profile"), dict) else {}
            outputs = a.get("outputs", {}) if isinstance(a.get("outputs"), dict) else {}
            writer.writerow(
                {
                    "attempt_index": int(a.get("attempt_index", 0) or 0),
                    "pass": bool(a.get("pass", False)),
                    "returncode": int(a.get("returncode", -1) or -1),
                    "speed_mode": str(profile.get("speed_mode", "")),
                    "speed_mode_replicas": int(profile.get("speed_mode_replicas", 0) or 0),
                    "speed_profile_max_replicas": int(profile.get("speed_profile_max_replicas", 0) or 0),
                    "reason": str(a.get("reason", "")),
                    "gate_json": str(outputs.get("gate_json", "")),
                    "gate_csv": str(outputs.get("gate_csv", "")),
                    "stage2_csv": str(outputs.get("stage2_csv", "")),
                    "benchmark_csv": str(outputs.get("benchmark_csv", "")),
                }
            )
    return out_path


def _load_targets_from_csv(path: str, *, max_targets: int = 0) -> List[str]:
    src = str(path).strip()
    if not src or (not os.path.exists(src)):
        return []
    df = pd.read_csv(src)
    if "target" not in df.columns:
        return []
    targets = []
    seen = set()
    for raw in df["target"].astype(str).tolist():
        t = str(raw).strip()
        if (not t) or (t in seen):
            continue
        seen.add(t)
        targets.append(t)
    if int(max_targets) > 0:
        targets = targets[: int(max_targets)]
    return targets


def _resolve_smoke_targets(cath_split_csv: str, cath_sources_csv: str, max_targets: int) -> List[str]:
    split_targets = _load_targets_from_csv(cath_split_csv, max_targets=0)
    if split_targets:
        return split_targets[: int(max_targets)]
    return _load_targets_from_csv(cath_sources_csv, max_targets=int(max_targets))


def _load_defaults(path: str) -> Dict[str, Any]:
    payload = _read_json_if_exists(path)
    defaults = payload.get("defaults", {}) if isinstance(payload.get("defaults"), dict) else {}
    return defaults


def _apply_defaults(args: argparse.Namespace, defaults: Dict[str, Any]) -> None:
    def _set_if_empty(name: str) -> None:
        cur = getattr(args, name, None)
        if cur is None:
            if name in defaults:
                setattr(args, name, defaults[name])
            return
        if isinstance(cur, str) and (not cur.strip()) and (name in defaults):
            setattr(args, name, defaults[name])

    keys = [
        "active_learning_ood_pair_csv",
        "active_learning_accuracy_external_csv",
        "active_learning_curriculum_base_manifest_csv",
        "active_learning_curriculum_checkpoint_dir",
        "active_learning_stage2_csv",
        "sentinel_sources_csv",
        "sentinel_targets",
        "cath_sources_csv",
        "cath_split_csv",
        "cath_manifest_csv",
        "special_case_policy_json",
        "special_case_metal_sources_csv",
        "special_case_dna_sources_csv",
        "special_case_membrane_sources_csv",
    ]
    for key in keys:
        _set_if_empty(key)


def _run_cmd(cmd: List[str], env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    started = time.time()
    proc = subprocess.run(cmd, env=env, text=True, capture_output=True)
    ended = time.time()
    return {
        "cmd": list(cmd),
        "cmd_str": _cmd_str(cmd),
        "returncode": int(proc.returncode),
        "ok": bool(proc.returncode == 0),
        "duration_sec": float(max(0.0, ended - started)),
        "stdout_tail": "\n".join((proc.stdout or "").splitlines()[-80:]),
        "stderr_tail": "\n".join((proc.stderr or "").splitlines()[-80:]),
    }


def _append_step(
    records: List[Dict[str, Any]],
    *,
    stage: str,
    scope: str,
    name: str,
    run_result: Dict[str, Any],
    outputs: Optional[Dict[str, Any]] = None,
    pass_flag: Optional[bool] = None,
    reason: str = "",
) -> Dict[str, Any]:
    rec = dict(run_result)
    rec["index"] = int(len(records) + 1)
    rec["stage"] = stage
    rec["scope"] = scope
    rec["name"] = name
    rec["outputs"] = dict(outputs or {})
    rec["pass"] = pass_flag
    rec["reason"] = str(reason or "")
    records.append(rec)
    return rec


def _build_gate_cmd(
    args: argparse.Namespace,
    out_prefix: str,
    attempt_idx: int,
    profile: Dict[str, Any],
) -> Tuple[List[str], Dict[str, str]]:
    attempt_prefix = f"{out_prefix}_gate_attempt{attempt_idx}"
    out_json = f"{attempt_prefix}.json"
    out_csv = f"{attempt_prefix}.csv"
    parity_prefix = f"{attempt_prefix}_parity"
    stage2_prefix = f"{attempt_prefix}_stage2"
    bench_csv = f"{attempt_prefix}_bench.csv"

    cmd = [
        sys.executable,
        "tools/validate_accuracy_gate.py",
        "--targets",
        str(args.gate_targets),
        "--samples",
        str(int(args.gate_samples)),
        "--noise",
        str(float(args.gate_noise)),
        "--steps",
        str(int(args.gate_steps)),
        "--runs",
        str(int(args.gate_runs)),
        "--warmup-steps",
        str(int(args.gate_warmup_steps)),
        "--strict-mode",
        "--enforce-speed-gate",
        "--jaccard-threshold",
        str(float(args.gate_jaccard_threshold)),
        "--e2e-rmse-threshold",
        str(float(args.gate_e2e_rmse_threshold)),
        "--rel-rmse-threshold",
        str(float(args.gate_rel_rmse_threshold)),
        "--speedup-threshold",
        str(float(args.gate_speedup_threshold)),
        "--speed-mode",
        str(profile.get("speed_mode", "balanced")),
        "--speed-mode-replicas",
        str(int(profile.get("speed_mode_replicas", 0))),
        "--speed-profile-max-replicas",
        str(int(profile.get("speed_profile_max_replicas", 0))),
        "--out-json",
        out_json,
        "--out-csv",
        out_csv,
        "--parity-prefix",
        parity_prefix,
        "--stage2-prefix",
        stage2_prefix,
        "--benchmark-csv",
        bench_csv,
    ]
    outputs = {
        "gate_json": out_json,
        "gate_csv": out_csv,
        "parity_prefix": parity_prefix,
        "stage2_prefix": stage2_prefix,
        "stage2_csv": f"{stage2_prefix}.csv",
        "stage2_json": f"{stage2_prefix}.json",
        "benchmark_csv": bench_csv,
    }
    return cmd, outputs


def _run_gate_with_retries(
    args: argparse.Namespace,
    out_prefix: str,
    env: Dict[str, str],
    records: List[Dict[str, Any]],
) -> Dict[str, Any]:
    retries = int(max(1, args.gate_retry_max))
    attempts: List[Dict[str, Any]] = []
    gate_pass = False
    passed_attempt_idx: Optional[int] = None
    passed_outputs: Dict[str, str] = {}

    for i in range(1, retries + 1):
        ladder_idx = min(i - 1, len(GATE_SPEED_LADDER) - 1)
        profile = dict(GATE_SPEED_LADDER[ladder_idx])
        cmd, outputs = _build_gate_cmd(args=args, out_prefix=out_prefix, attempt_idx=i, profile=profile)
        run_result = _run_cmd(cmd, env=env)
        gate_payload = _read_json_if_exists(outputs["gate_json"])
        gate_summary = gate_payload.get("summary", {}) if isinstance(gate_payload.get("summary"), dict) else {}
        this_pass = bool(gate_summary.get("pass", False))

        reason = ""
        if not this_pass:
            failed_metrics = gate_summary.get("failed_metrics", [])
            if isinstance(failed_metrics, list) and failed_metrics:
                reason = f"failed_metrics={failed_metrics[:3]}"
            else:
                reason = "gate_pass=false"

        step_rec = _append_step(
            records,
            stage="stage1_gate",
            scope="retry",
            name=f"gate_attempt_{i}",
            run_result=run_result,
            outputs=outputs,
            pass_flag=this_pass,
            reason=reason,
        )
        attempt_payload = {
            "attempt_index": i,
            "profile": profile,
            "pass": this_pass,
            "returncode": int(run_result.get("returncode", -1)),
            "outputs": outputs,
            "reason": reason,
            "stderr_tail": str(run_result.get("stderr_tail", "")),
            "stdout_tail": str(run_result.get("stdout_tail", "")),
            "step_index": int(step_rec["index"]),
        }
        attempts.append(attempt_payload)
        if this_pass:
            gate_pass = True
            passed_attempt_idx = i
            passed_outputs = outputs
            break

    return {
        "pass": gate_pass,
        "attempts": attempts,
        "passed_attempt_index": passed_attempt_idx,
        "passed_outputs": passed_outputs,
    }


def _run_stage4(
    *,
    args: argparse.Namespace,
    scope: str,
    out_prefix: str,
    env: Dict[str, str],
    stage2_csv: str,
    records: List[Dict[str, Any]],
) -> Dict[str, Any]:
    stage_prefix = f"{out_prefix}_stage4_{scope}"
    topk = int(args.active_learning_topk_smoke if scope == "smoke" else args.active_learning_topk_full)
    targets = str(args.active_learning_smoke_targets if scope == "smoke" else args.active_learning_full_targets)
    curriculum_max_targets = int(
        args.active_learning_curriculum_max_targets_smoke
        if scope == "smoke"
        else args.active_learning_curriculum_max_targets_full
    )
    cmd = [
        sys.executable,
        "tools/run_active_learning_cycle.py",
        "--date-tag",
        str(args.date_tag),
        "--targets",
        targets,
        "--out-prefix",
        stage_prefix,
        "--ood-pair-csv",
        str(args.active_learning_ood_pair_csv),
        "--accuracy-external-csv",
        str(args.active_learning_accuracy_external_csv),
        "--stage2-csv",
        str(stage2_csv),
        "--hard-mining-topk",
        str(topk),
        "--curriculum-base-manifest-csv",
        str(args.active_learning_curriculum_base_manifest_csv),
        "--curriculum-checkpoint-dir",
        str(args.active_learning_curriculum_checkpoint_dir),
        "--curriculum-max-targets",
        str(max(curriculum_max_targets, 0)),
    ]
    if bool(args.active_learning_skip_claim_correction):
        cmd.append("--skip-claim-correction")
    else:
        cmd.append("--no-skip-claim-correction")
    if bool(args.active_learning_skip_curriculum_training):
        cmd.append("--skip-curriculum-training")

    run_result = _run_cmd(cmd, env=env)
    summary_json = f"{stage_prefix}_summary.json"
    payload = _read_json_if_exists(summary_json)
    passed = bool(payload.get("pass", False))
    reason = "" if passed else "stage4 pass=false"
    _append_step(
        records,
        stage="stage4_active_learning",
        scope=scope,
        name=f"stage4_active_learning_{scope}",
        run_result=run_result,
        outputs={"summary_json": summary_json, "summary_md": f"{stage_prefix}_summary.md"},
        pass_flag=passed,
        reason=reason,
    )
    return {"pass": passed, "reason": reason, "summary_json": summary_json}


def _run_stage5(
    *,
    args: argparse.Namespace,
    scope: str,
    out_prefix: str,
    env: Dict[str, str],
    records: List[Dict[str, Any]],
) -> Dict[str, Any]:
    stage_prefix = f"{out_prefix}_stage5_{scope}"
    min_pairs = int(args.sentinel_min_pairs_smoke if scope == "smoke" else args.sentinel_min_pairs_full)
    max_pair_rmsd = float(
        args.sentinel_max_mean_pair_rmsd_smoke
        if scope == "smoke"
        else args.sentinel_max_mean_pair_rmsd_full
    )
    out_dir = f"data/public_structures/post_gate_pipeline/{args.date_tag}/stage5_{scope}"
    cmd = [
        sys.executable,
        "tools/run_ood_first_validation_batch.py",
        "--targets",
        str(args.sentinel_targets),
        "--date-tag",
        f"{args.date_tag}_stage5_{scope}",
        "--sources-csv",
        str(args.sentinel_sources_csv),
        "--out-dir",
        out_dir,
        "--out-prefix",
        stage_prefix,
        "--download-pdb",
        "--no-download-afdb",
        "--enable-proxy-manifest",
        "--min-pairs",
        str(min_pairs),
        "--max-mean-pair-rmsd",
        str(max_pair_rmsd),
        "--strict-fail",
    ]
    run_result = _run_cmd(cmd, env=env)
    summary_json = f"{stage_prefix}_summary.json"
    payload = _read_json_if_exists(summary_json)
    passed = bool(payload.get("pass", False))
    reason = "" if passed else "stage5 pass=false"
    _append_step(
        records,
        stage="stage5_sentinel_ood",
        scope=scope,
        name=f"stage5_sentinel_ood_{scope}",
        run_result=run_result,
        outputs={"summary_json": summary_json, "pair_csv": f"{stage_prefix}_pair_metrics.csv"},
        pass_flag=passed,
        reason=reason,
    )
    return {
        "pass": passed,
        "reason": reason,
        "summary_json": summary_json,
        "pair_csv": f"{stage_prefix}_pair_metrics.csv",
    }


def _run_stage6(
    *,
    args: argparse.Namespace,
    scope: str,
    out_prefix: str,
    env: Dict[str, str],
    records: List[Dict[str, Any]],
) -> Dict[str, Any]:
    stage_prefix = f"{out_prefix}_stage6_{scope}"
    out_dir = f"data/public_structures/post_gate_pipeline/{args.date_tag}/stage6_{scope}"
    if scope == "smoke":
        smoke_targets = _resolve_smoke_targets(
            cath_split_csv=str(args.cath_split_csv),
            cath_sources_csv=str(args.cath_sources_csv),
            max_targets=int(args.stage6_smoke_max_targets),
        )
        targets_spec = ",".join(smoke_targets)
    else:
        full_targets = _load_targets_from_csv(str(args.cath_sources_csv), max_targets=0)
        targets_spec = ",".join(full_targets)

    manifest_csv = (
        f"{stage_prefix}_manifest.csv"
        if scope == "smoke"
        else (str(args.cath_manifest_csv).strip() or f"{stage_prefix}_manifest.csv")
    )
    fetch_summary_json = f"{stage_prefix}_fetch_summary.json"
    curated_csv = f"{stage_prefix}_curated.csv"
    curated_json = f"{stage_prefix}_curated.json"
    noise_csv = f"{stage_prefix}_noise.csv"
    noise_json = f"{stage_prefix}_noise_summary.json"
    variants = int(args.stage6_variants_smoke if scope == "smoke" else args.stage6_variants_full)

    substeps: List[Tuple[str, List[str], Dict[str, Any]]] = [
        (
            "stage6_fetch",
            [
                sys.executable,
                "tools/fetch_public_structure_set.py",
                "--sources-csv",
                str(args.cath_sources_csv),
                "--targets",
                str(targets_spec),
                "--out-dir",
                out_dir,
                "--out-manifest-csv",
                manifest_csv,
                "--out-summary-json",
                fetch_summary_json,
                "--download-pdb",
                "--no-download-afdb",
            ],
            {"manifest_csv": manifest_csv, "summary_json": fetch_summary_json},
        ),
        (
            "stage6_curate",
            [
                sys.executable,
                "tools/curate_structure_quality.py",
                "--manifest-csv",
                manifest_csv,
                "--out-csv",
                curated_csv,
                "--out-json",
                curated_json,
            ],
            {"curated_csv": curated_csv, "curated_json": curated_json},
        ),
        (
            "stage6_noise_augmentation",
            [
                sys.executable,
                "tools/build_cath_noise_augmentation.py",
                "--manifest-csv",
                manifest_csv,
                "--variants-per-target",
                str(variants),
                "--out-csv",
                noise_csv,
                "--out-json",
                noise_json,
            ],
            {"noise_csv": noise_csv, "noise_json": noise_json},
        ),
    ]

    stage_pass = True
    failed_reason = ""
    for sub_name, cmd, outputs in substeps:
        run_result = _run_cmd(cmd, env=env)
        step_pass = bool(run_result.get("ok", False))
        reason = "" if step_pass else f"{sub_name} returncode={run_result.get('returncode')}"

        if step_pass and sub_name == "stage6_noise_augmentation":
            payload = _read_json_if_exists(noise_json)
            summary = payload.get("summary", {}) if isinstance(payload.get("summary"), dict) else {}
            rows_total = int(summary.get("rows_total", 0) or 0)
            if rows_total <= 0:
                step_pass = False
                reason = "noise_augmentation_rows_total<=0"

        _append_step(
            records,
            stage="stage6_large_screening",
            scope=scope,
            name=f"{sub_name}_{scope}",
            run_result=run_result,
            outputs=outputs,
            pass_flag=step_pass,
            reason=reason,
        )
        if not step_pass:
            stage_pass = False
            failed_reason = reason
            break

    return {
        "pass": stage_pass,
        "reason": failed_reason,
        "manifest_csv": manifest_csv,
        "fetch_summary_json": fetch_summary_json,
        "curated_csv": curated_csv,
        "curated_json": curated_json,
        "noise_csv": noise_csv,
        "noise_json": noise_json,
    }


def _run_special_case_stage(
    *,
    args: argparse.Namespace,
    scope: str,
    out_prefix: str,
    env: Dict[str, str],
    records: List[Dict[str, Any]],
    domain: str,
    stage_name: str,
    gate_json: str,
) -> Dict[str, Any]:
    stage_prefix = f"{out_prefix}_{stage_name}_{scope}"
    run_scope = "smoke_only" if scope == "smoke" else "full_only"
    cmd = [
        sys.executable,
        "tools/run_special_case_pipeline.py",
        "--date-tag",
        str(args.date_tag),
        "--domains",
        str(domain),
        "--run-scope",
        run_scope,
        "--strict-fail-fast",
        "--skip-core-gate",
        "--core-gate-json",
        str(gate_json),
        "--policy-json",
        str(args.special_case_policy_json),
        "--metal-sources-csv",
        str(args.special_case_metal_sources_csv),
        "--dna-sources-csv",
        str(args.special_case_dna_sources_csv),
        "--membrane-sources-csv",
        str(args.special_case_membrane_sources_csv),
        "--out-prefix",
        stage_prefix,
    ]
    if str(args.special_case_strict_summary_json).strip():
        cmd.extend(["--strict-summary-json", str(args.special_case_strict_summary_json)])

    run_result = _run_cmd(cmd, env=env)
    summary_json = f"{stage_prefix}_summary.json"
    payload = _read_json_if_exists(summary_json)
    passed = bool(payload.get("pass", False))
    reason = "" if passed else f"{stage_name} pass=false"
    _append_step(
        records,
        stage=stage_name,
        scope=scope,
        name=f"{stage_name}_{scope}",
        run_result=run_result,
        outputs={"summary_json": summary_json, "summary_md": f"{stage_prefix}_summary.md"},
        pass_flag=passed,
        reason=reason,
    )
    return {"pass": passed, "reason": reason, "summary_json": summary_json}


def _write_summary_md(path: str, payload: Dict[str, Any]) -> None:
    _ensure_parent(path)
    lines: List[str] = []
    lines.append("# Post Gate Pipeline Summary")
    lines.append("")
    lines.append(f"- generated_at_local: `{payload.get('generated_at_local')}`")
    lines.append(f"- date_tag: `{payload.get('date_tag')}`")
    lines.append(f"- run_scope: `{payload.get('run_scope')}`")
    lines.append(f"- pass: `{payload.get('pass')}`")
    lines.append(f"- exit_code: `{payload.get('exit_code')}`")
    lines.append(f"- failed_stage: `{payload.get('failed_stage')}`")
    lines.append("")
    gate = payload.get("stage1_gate", {})
    lines.append("## Stage-1 Gate")
    lines.append(f"- pass: `{gate.get('pass')}`")
    lines.append(f"- attempts: `{len(gate.get('attempts', []))}`")
    lines.append(f"- passed_attempt_index: `{gate.get('passed_attempt_index')}`")
    lines.append(f"- attempts_csv: `{gate.get('attempts_csv')}`")
    lines.append("")
    lines.append("## Stage Status")
    stage_map = payload.get("stages", {})
    for key in ["stage4", "stage5", "stage6", "stage7_metal", "stage8_dna", "stage9_membrane"]:
        item = stage_map.get(key, {})
        lines.append(f"- {key}: `{item.get('pass')}`")
        lines.append(f"  smoke: `{item.get('smoke', {}).get('pass')}`")
        lines.append(f"  full: `{item.get('full', {}).get('pass')}`")
    lines.append("")
    lines.append("## Artifacts")
    artifacts = payload.get("artifacts", {})
    lines.append(f"- summary_json: `{artifacts.get('summary_json')}`")
    lines.append(f"- summary_md: `{artifacts.get('summary_md')}`")
    lines.append(f"- steps_csv: `{artifacts.get('steps_csv')}`")
    lines.append(f"- gate_attempts_csv: `{artifacts.get('gate_attempts_csv')}`")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def _run_scope_list(run_scope: str) -> List[str]:
    s = str(run_scope).strip().lower()
    if s == "smoke_only":
        return ["smoke"]
    if s == "full_only":
        return ["full"]
    return ["smoke", "full"]


def run_pipeline(args: argparse.Namespace) -> Dict[str, Any]:
    date_tag = str(args.date_tag).strip() or dt.date.today().isoformat()
    out_prefix = str(args.out_prefix).strip() or f"runs/post_gate_pipeline_{date_tag}"
    summary_json = f"{out_prefix}_summary.json"
    summary_md = f"{out_prefix}_summary.md"
    steps_csv = f"{out_prefix}_steps.csv"

    defaults = _load_defaults(str(args.defaults_json))
    _apply_defaults(args, defaults)

    env = os.environ.copy()
    env["FORCE_RUST_HIP"] = "1"
    env["RUST_HIP_USE_GPU_NBLIST_BUILDER"] = "1"

    records: List[Dict[str, Any]] = []
    failed_stage = ""
    failed_reason = ""
    exit_code = 0

    gate_info = _run_gate_with_retries(
        args=args,
        out_prefix=out_prefix,
        env=env,
        records=records,
    )
    gate_attempts_csv = _write_gate_attempts_csv(
        f"{out_prefix}_gate_attempts.csv",
        gate_info.get("attempts", []) if isinstance(gate_info.get("attempts"), list) else [],
    )
    gate_info["attempts_csv"] = gate_attempts_csv
    if not bool(gate_info.get("pass", False)):
        failed_stage = "stage1_gate"
        failed_reason = "all_gate_attempts_failed"
        exit_code = 2
    else:
        gate_stage2_csv = str(gate_info.get("passed_outputs", {}).get("stage2_csv", "")).strip()
        if (not gate_stage2_csv) or (not os.path.exists(gate_stage2_csv)):
            gate_stage2_csv = str(args.active_learning_stage2_csv).strip()
        scopes = _run_scope_list(str(args.run_scope))
        stage_results: Dict[str, Dict[str, Any]] = {
            "stage4": {"smoke": {}, "full": {}, "pass": False},
            "stage5": {"smoke": {}, "full": {}, "pass": False},
            "stage6": {"smoke": {}, "full": {}, "pass": False},
            "stage7_metal": {"smoke": {}, "full": {}, "pass": False},
            "stage8_dna": {"smoke": {}, "full": {}, "pass": False},
            "stage9_membrane": {"smoke": {}, "full": {}, "pass": False},
        }

        def _handle_stage_result(stage_key: str, scope: str, result: Dict[str, Any]) -> bool:
            nonlocal failed_stage, failed_reason, exit_code
            stage_results[stage_key][scope] = result
            if not bool(result.get("pass", False)):
                failed_stage = f"{stage_key}_{scope}"
                failed_reason = str(result.get("reason", "") or "stage_failed")
                exit_code = 3
                return False
            return True

        if exit_code == 0:
            for scope in scopes:
                stage4 = _run_stage4(
                    args=args,
                    scope=scope,
                    out_prefix=out_prefix,
                    env=env,
                    stage2_csv=gate_stage2_csv,
                    records=records,
                )
                if not _handle_stage_result("stage4", scope, stage4):
                    if bool(args.strict_fail_fast):
                        break
            stage_results["stage4"]["pass"] = bool(
                stage_results["stage4"].get("smoke", {}).get("pass", False)
                and (("full" not in scopes) or stage_results["stage4"].get("full", {}).get("pass", False))
            )

        if exit_code == 0:
            for scope in scopes:
                stage5 = _run_stage5(
                    args=args,
                    scope=scope,
                    out_prefix=out_prefix,
                    env=env,
                    records=records,
                )
                if not _handle_stage_result("stage5", scope, stage5):
                    if bool(args.strict_fail_fast):
                        break
            stage_results["stage5"]["pass"] = bool(
                stage_results["stage5"].get("smoke", {}).get("pass", False)
                and (("full" not in scopes) or stage_results["stage5"].get("full", {}).get("pass", False))
            )

        if exit_code == 0:
            for scope in scopes:
                stage6 = _run_stage6(
                    args=args,
                    scope=scope,
                    out_prefix=out_prefix,
                    env=env,
                    records=records,
                )
                if not _handle_stage_result("stage6", scope, stage6):
                    if bool(args.strict_fail_fast):
                        break
            stage_results["stage6"]["pass"] = bool(
                stage_results["stage6"].get("smoke", {}).get("pass", False)
                and (("full" not in scopes) or stage_results["stage6"].get("full", {}).get("pass", False))
            )

        if exit_code == 0 and bool(args.run_special_cases):
            gate_json = str(gate_info.get("passed_outputs", {}).get("gate_json", "")).strip()
            stage_specs = [
                ("stage7_metal", "metal"),
                ("stage8_dna", "dna"),
                ("stage9_membrane", "membrane"),
            ]
            for stage_key, domain in stage_specs:
                for scope in scopes:
                    stage_out = _run_special_case_stage(
                        args=args,
                        scope=scope,
                        out_prefix=out_prefix,
                        env=env,
                        records=records,
                        domain=domain,
                        stage_name=stage_key,
                        gate_json=gate_json,
                    )
                    if not _handle_stage_result(stage_key, scope, stage_out):
                        if bool(args.strict_fail_fast):
                            break
                stage_results[stage_key]["pass"] = bool(
                    stage_results[stage_key].get("smoke", {}).get("pass", False)
                    and (("full" not in scopes) or stage_results[stage_key].get("full", {}).get("pass", False))
                )
                if exit_code != 0 and bool(args.strict_fail_fast):
                    break
    # Summary
    pass_all = bool(exit_code == 0)
    stage_results = stage_results if "stage_results" in locals() else {
        "stage4": {"smoke": {}, "full": {}, "pass": False},
        "stage5": {"smoke": {}, "full": {}, "pass": False},
        "stage6": {"smoke": {}, "full": {}, "pass": False},
        "stage7_metal": {"smoke": {}, "full": {}, "pass": False},
        "stage8_dna": {"smoke": {}, "full": {}, "pass": False},
        "stage9_membrane": {"smoke": {}, "full": {}, "pass": False},
    }
    summary_payload: Dict[str, Any] = {
        "generated_at_local": _now_iso(),
        "date_tag": date_tag,
        "run_scope": str(args.run_scope),
        "pass": pass_all,
        "exit_code": int(exit_code),
        "failed_stage": failed_stage or None,
        "failed_reason": failed_reason or None,
        "stage1_gate": gate_info,
        "stages": stage_results,
        "steps": records,
        "artifacts": {
            "summary_json": summary_json,
            "summary_md": summary_md,
            "steps_csv": steps_csv,
            "gate_attempts_csv": gate_attempts_csv,
        },
    }

    _ensure_parent(summary_json)
    with open(summary_json, "w", encoding="utf-8") as f:
        json.dump(summary_payload, f, indent=2, ensure_ascii=False)

    if records:
        step_df = pd.DataFrame(records)
    else:
        step_df = pd.DataFrame(
            columns=[
                "index",
                "stage",
                "scope",
                "name",
                "cmd_str",
                "returncode",
                "ok",
                "pass",
                "reason",
                "duration_sec",
                "stdout_tail",
                "stderr_tail",
            ]
        )
    _ensure_parent(steps_csv)
    step_df.to_csv(steps_csv, index=False)
    _write_summary_md(summary_md, summary_payload)
    return summary_payload


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Post-gate orchestration: retry strict gate (up to N), then auto-run "
            "Stage-4/5/6/7/8/9 in smoke -> full sequence."
        )
    )
    p.add_argument("--defaults-json", type=str, default="config/post_gate_pipeline_defaults.json")
    p.add_argument("--date-tag", type=str, default=dt.date.today().isoformat())
    p.add_argument("--run-scope", type=str, default="smoke_then_full", choices=["smoke_then_full", "smoke_only", "full_only"])
    p.add_argument("--out-prefix", type=str, default="")
    p.add_argument("--strict-fail-fast", action=argparse.BooleanOptionalAction, default=True)

    # Stage-1 gate
    p.add_argument("--gate-retry-max", type=int, default=5)
    p.add_argument("--gate-targets", type=str, default="all")
    p.add_argument("--gate-samples", type=int, default=8)
    p.add_argument("--gate-noise", type=float, default=0.08)
    p.add_argument("--gate-steps", type=int, default=60)
    p.add_argument("--gate-runs", type=int, default=1)
    p.add_argument("--gate-warmup-steps", type=int, default=40)
    p.add_argument("--gate-jaccard-threshold", type=float, default=1.0)
    p.add_argument("--gate-e2e-rmse-threshold", type=float, default=0.35)
    p.add_argument("--gate-rel-rmse-threshold", type=float, default=1e-5)
    p.add_argument("--gate-speedup-threshold", type=float, default=12.0)

    # Stage-4
    p.add_argument("--active-learning-topk-smoke", type=int, default=1)
    p.add_argument("--active-learning-topk-full", type=int, default=4)
    p.add_argument("--active-learning-smoke-targets", type=str, default="Chignolin")
    p.add_argument("--active-learning-full-targets", type=str, default="all")
    p.add_argument("--active-learning-curriculum-max-targets-smoke", type=int, default=1)
    p.add_argument("--active-learning-curriculum-max-targets-full", type=int, default=0)
    p.add_argument("--active-learning-ood-pair-csv", type=str, default="")
    p.add_argument("--active-learning-accuracy-external-csv", type=str, default="")
    p.add_argument("--active-learning-curriculum-base-manifest-csv", type=str, default="")
    p.add_argument("--active-learning-curriculum-checkpoint-dir", type=str, default="")
    p.add_argument("--active-learning-stage2-csv", type=str, default="")
    p.add_argument("--active-learning-skip-claim-correction", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--active-learning-skip-curriculum-training", action=argparse.BooleanOptionalAction, default=False)

    # Stage-5
    p.add_argument("--sentinel-sources-csv", type=str, default="config/structure_sources_sentinel.csv")
    p.add_argument("--sentinel-targets", type=str, default="Hemoglobin_4HHB")
    p.add_argument("--sentinel-min-pairs-smoke", type=int, default=1)
    p.add_argument("--sentinel-min-pairs-full", type=int, default=1)
    p.add_argument("--sentinel-max-mean-pair-rmsd-smoke", type=float, default=12.0)
    p.add_argument("--sentinel-max-mean-pair-rmsd-full", type=float, default=8.0)

    # Stage-6
    p.add_argument("--cath-sources-csv", type=str, default="config/cath_sources_100_2026-02-19.csv")
    p.add_argument("--cath-split-csv", type=str, default="runs/cath_diversity_100_split_2026-02-19.csv")
    p.add_argument("--cath-manifest-csv", type=str, default="")
    p.add_argument("--stage6-smoke-max-targets", type=int, default=10)
    p.add_argument("--stage6-variants-smoke", type=int, default=4)
    p.add_argument("--stage6-variants-full", type=int, default=12)

    # Stage-7/8/9 special-case domains
    p.add_argument("--run-special-cases", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument(
        "--special-case-policy-json",
        type=str,
        default="config/special_case_gate_policy_v1_2026-02-18.json",
    )
    p.add_argument(
        "--special-case-metal-sources-csv",
        type=str,
        default="config/structure_sources_special_metal.csv",
    )
    p.add_argument(
        "--special-case-dna-sources-csv",
        type=str,
        default="config/structure_sources_special_dna.csv",
    )
    p.add_argument(
        "--special-case-membrane-sources-csv",
        type=str,
        default="config/structure_sources_special_membrane.csv",
    )
    p.add_argument("--special-case-strict-summary-json", type=str, default="")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = run_pipeline(args)
    out = {
        "pass": bool(payload.get("pass", False)),
        "exit_code": int(payload.get("exit_code", 1)),
        "failed_stage": payload.get("failed_stage"),
        "summary_json": payload.get("artifacts", {}).get("summary_json"),
        "summary_md": payload.get("artifacts", {}).get("summary_md"),
        "steps_csv": payload.get("artifacts", {}).get("steps_csv"),
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))
    if int(out["exit_code"]) != 0:
        sys.exit(int(out["exit_code"]))


if __name__ == "__main__":
    main()
