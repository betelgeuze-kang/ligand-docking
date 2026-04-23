#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import datetime as dt
import glob
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

from tools.speed_profile_defaults import load_speed_profile_section, resolve_speed_profile


def _safe_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except Exception:
        return None


_VALID_AI_RUNTIME_MODES = {"eager", "scripted", "compiled", "onnx"}


def _cmd_to_str(cmd: List[str]) -> str:
    return " ".join(cmd)


def _run_cmd(cmd: List[str], env: Optional[Dict[str, str]] = None, dry_run: bool = False) -> Dict[str, Any]:
    rec: Dict[str, Any] = {
        "cmd": cmd,
        "cmd_str": _cmd_to_str(cmd),
        "dry_run": bool(dry_run),
        "returncode": 0,
        "ok": True,
    }
    if dry_run:
        return rec
    proc = subprocess.run(cmd, env=env, text=True, capture_output=True)
    rec["returncode"] = int(proc.returncode)
    rec["ok"] = bool(proc.returncode == 0)
    rec["stdout_tail"] = "\n".join((proc.stdout or "").splitlines()[-40:])
    rec["stderr_tail"] = "\n".join((proc.stderr or "").splitlines()[-40:])
    return rec


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


def _resolve_dashboard_compare_csv(
    runs_dir: str,
    *,
    explicit_compare_csv: str,
    current_feature_csv: str,
) -> str:
    explicit = _resolve_input_path(str(explicit_compare_csv).strip())
    if explicit and os.path.exists(explicit):
        return explicit

    root = str(runs_dir).strip() or "runs"
    pattern = os.path.join(root, "feature_matrix_per_target_nightly_*.csv")
    cur_abs = os.path.abspath(str(current_feature_csv))
    candidates: List[str] = []
    for path in glob.glob(pattern):
        ap = os.path.abspath(str(path))
        if ap == cur_abs:
            continue
        if os.path.isfile(ap):
            candidates.append(ap)
    if not candidates:
        return ""
    candidates = sorted(candidates, key=lambda p: os.path.getmtime(p), reverse=True)
    return str(candidates[0])


def _resolve_latest_attempts_csv(root: str, patterns: List[str]) -> str:
    candidates: List[str] = []
    for pat in patterns:
        full_pat = os.path.join(root, pat)
        for src in glob.glob(full_pat):
            ap = os.path.abspath(str(src))
            if os.path.isfile(ap):
                candidates.append(ap)
    if not candidates:
        return ""
    candidates = sorted(set(candidates), key=lambda p: os.path.getmtime(p), reverse=True)
    return str(candidates[0])


def _resolve_attempts_csv_links(runs_dir: str, date_tag: str) -> Dict[str, str]:
    root = str(runs_dir).strip() or "runs"
    return {
        "accuracy_revalidation_attempts_csv": _resolve_latest_attempts_csv(
            root,
            [
                f"accuracy_revalidation_{date_tag}*_attempts.csv",
                "accuracy_revalidation_*_attempts.csv",
            ],
        ),
        "post_gate_pipeline_attempts_csv": _resolve_latest_attempts_csv(
            root,
            [
                f"post_gate_pipeline_{date_tag}*_gate_attempts.csv",
                "post_gate_pipeline_*_gate_attempts.csv",
            ],
        ),
    }


def _csv_header(path: str) -> List[str]:
    src = str(path).strip()
    if (not src) or (not os.path.exists(src)):
        return []
    try:
        with open(src, "r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            row = next(reader, [])
            return [str(x).strip() for x in row]
    except Exception:
        return []


def _csv_nonempty_count(path: str, col: str, *, max_rows: int = 200000) -> int:
    src = str(path).strip()
    key = str(col).strip()
    if (not src) or (not key) or (not os.path.exists(src)):
        return 0
    try:
        with open(src, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            n = 0
            for i, row in enumerate(reader):
                if i >= int(max_rows):
                    break
                v = str((row or {}).get(key, "")).strip()
                if v:
                    n += 1
            return int(n)
    except Exception:
        return 0


def _csv_unique_nonempty_count(path: str, col: str, *, max_rows: int = 200000) -> int:
    src = str(path).strip()
    key = str(col).strip()
    if (not src) or (not key) or (not os.path.exists(src)):
        return 0
    try:
        values = set()
        with open(src, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if i >= int(max_rows):
                    break
                v = str((row or {}).get(key, "")).strip()
                if v:
                    values.add(v)
        return int(len(values))
    except Exception:
        return 0


def _is_smoke_like_path(path: str) -> bool:
    name = os.path.basename(str(path).strip()).lower()
    return ("smoke" in name) or ("_r1" in name and "full" not in name)


def _summarize_accuracy_external_candidate(path: str, source: str) -> Dict[str, Any]:
    src = str(path).strip()
    header = _csv_header(src)
    has_target = "target" in header
    has_ref = "reference_source" in header
    has_rmsd = ("avg_rmsd" in header) or ("avg_rmsd_aligned" in header)
    return {
        "path": src,
        "source": str(source),
        "exists": bool(src and os.path.exists(src)),
        "is_smoke_path": _is_smoke_like_path(src),
        "has_target_col": bool(has_target),
        "has_reference_source_col": bool(has_ref),
        "has_rmsd_cols": bool(has_rmsd),
        "targets": int(_csv_unique_nonempty_count(src, "target")) if has_target else 0,
        "reference_source_nonempty_rows": int(_csv_nonempty_count(src, "reference_source")) if has_ref else 0,
        "mtime": float(os.path.getmtime(src)) if (src and os.path.exists(src)) else 0.0,
    }


def _resolve_external_packet_accuracy_external_csv(
    *,
    args: argparse.Namespace,
    paths: Dict[str, str],
    strict_summary_json_path: str,
) -> Tuple[str, List[Dict[str, Any]]]:
    candidates: List[Dict[str, Any]] = []
    seen: set[str] = set()

    def _append(path: str, source: str) -> None:
        p = _resolve_input_path(str(path).strip())
        if (not p) or (not os.path.exists(p)) or (p in seen):
            return
        seen.add(p)
        candidates.append(_summarize_accuracy_external_candidate(p, source))

    _append(str(getattr(args, "external_packet_accuracy_external_csv", "")).strip(), "explicit_external_packet")
    _append(str(getattr(args, "accuracy_external_csv", "")).strip(), "nightly_accuracy_external")
    rp = str(paths.get("rebench_prefix", "")).strip()
    if rp:
        _append(f"{rp}_speed_accuracy.csv", "rebench_speed_accuracy")
        _append(f"{rp}_accuracy.csv", "rebench_accuracy")

    strict_path = _resolve_input_path(str(strict_summary_json_path).strip())
    if strict_path:
        _append(strict_path.replace("_summary.json", "_accuracy_external.csv"), "strict_summary_sibling")
        sdir = os.path.dirname(strict_path)
        if sdir and os.path.isdir(sdir):
            for p in sorted(glob.glob(os.path.join(sdir, "*accuracy_external*.csv"))):
                _append(p, "strict_summary_dir_glob")

    for p in sorted(glob.glob("runs/**/*accuracy_external*.csv", recursive=True)):
        _append(p, "auto_glob_accuracy_external")

    if not candidates:
        return "", []

    def _rank(rec: Dict[str, Any]) -> Tuple[int, int, int, int, int, int, float]:
        targets = int(rec.get("targets", 0) or 0)
        ref_non = int(rec.get("reference_source_nonempty_rows", 0) or 0)
        full_target = 1 if targets >= 10 else 0
        enough_ref = 1 if ref_non >= 5 else 0
        has_req = 1 if (rec.get("has_target_col") and rec.get("has_rmsd_cols")) else 0
        not_smoke = 1 if (not bool(rec.get("is_smoke_path", False))) else 0
        mtime = float(rec.get("mtime", 0.0) or 0.0)
        return (full_target, enough_ref, has_req, targets, ref_non, not_smoke, mtime)

    chosen = sorted(candidates, key=_rank)[-1]
    return str(chosen.get("path", "")), candidates


def _sha256_file(path: str) -> Optional[str]:
    src = str(path).strip()
    if (not src) or (not os.path.exists(src)):
        return None
    h = hashlib.sha256()
    try:
        with open(src, "rb") as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def _git_rev_parse(arg: str) -> str:
    try:
        p = subprocess.run(
            ["git", "rev-parse", arg],
            text=True,
            capture_output=True,
            check=False,
        )
        if p.returncode == 0:
            return str((p.stdout or "").strip())
    except Exception:
        pass
    return ""


def _preflight_validate_inputs(
    *,
    args: argparse.Namespace,
    strict_summary_json_path: str,
    external_manifest_path: str,
    external_packet_accuracy_external_csv_path: str,
    claim_policy_json_path: str,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "enabled": bool(getattr(args, "preflight_validate_inputs", True)),
        "pass": True,
        "checks": [],
        "failures": [],
    }
    if not bool(getattr(args, "preflight_validate_inputs", True)):
        out["skipped"] = "disabled"
        return out
    if bool(getattr(args, "dry_run", False)):
        out["skipped"] = "dry_run"
        return out

    def _add_check(name: str, ok: bool, detail: Any) -> None:
        rec = {"name": str(name), "ok": bool(ok), "detail": detail}
        out["checks"].append(rec)
        if not ok:
            out["failures"].append(rec)

    strict_exists = bool(strict_summary_json_path and os.path.exists(strict_summary_json_path))
    strict_payload = _read_json_if_exists(strict_summary_json_path) if strict_exists else {}
    strict_ok = strict_exists and isinstance(strict_payload.get("summary"), dict)
    _add_check(
        "strict_summary_json",
        strict_ok,
        {"path": strict_summary_json_path, "exists": strict_exists, "has_summary": bool(strict_payload.get("summary"))},
    )

    manifest_exists = bool(external_manifest_path and os.path.exists(external_manifest_path))
    manifest_header = _csv_header(external_manifest_path) if manifest_exists else []
    manifest_required = {"target", "path"}
    manifest_missing = sorted(list(manifest_required - set(manifest_header)))
    manifest_ok = manifest_exists and (len(manifest_missing) == 0)
    _add_check(
        "external_manifest_csv",
        manifest_ok,
        {
            "path": external_manifest_path,
            "exists": manifest_exists,
            "missing_columns": manifest_missing,
        },
    )

    claim_policy_exists = bool(claim_policy_json_path and os.path.exists(claim_policy_json_path))
    claim_policy_payload = _read_json_if_exists(claim_policy_json_path) if claim_policy_exists else {}
    _add_check(
        "claim_policy_json",
        claim_policy_exists and bool(claim_policy_payload),
        {"path": claim_policy_json_path, "exists": claim_policy_exists},
    )

    require_ext_accuracy = bool(
        bool(getattr(args, "run_commercial_readiness", True))
        and bool(getattr(args, "commercial_readiness_enforce_pass", False))
        and int(getattr(args, "commercial_readiness_min_external_targets", 0) or 0) > 0
    )
    if require_ext_accuracy:
        acc_path = str(external_packet_accuracy_external_csv_path).strip()
        acc_exists = bool(acc_path and os.path.exists(acc_path))
        acc_header = _csv_header(acc_path) if acc_exists else []
        acc_required = {"target", "reference_source"}
        acc_missing = sorted(list(acc_required - set(acc_header)))
        ref_nonempty = _csv_nonempty_count(acc_path, "reference_source") if acc_exists else 0
        min_ext = int(getattr(args, "commercial_readiness_min_external_targets", 5))
        acc_ok = acc_exists and (len(acc_missing) == 0) and (ref_nonempty >= min_ext)
        _add_check(
            "external_accuracy_csv_for_commercial_gate",
            acc_ok,
            {
                "path": acc_path,
                "exists": acc_exists,
                "missing_columns": acc_missing,
                "reference_source_nonempty_rows": int(ref_nonempty),
                "required_min_rows": int(min_ext),
            },
        )

    out["pass"] = bool(len(out["failures"]) == 0)
    return out


def _write_reproducibility_snapshot(
    *,
    args: argparse.Namespace,
    paths: Dict[str, str],
    summary: Dict[str, Any],
    resolved_inputs: Dict[str, Any],
    env: Dict[str, str],
) -> Dict[str, Any]:
    out_path = str(paths.get("repro_snapshot_json", "")).strip()
    if not out_path:
        return {}

    git_head = _git_rev_parse("HEAD")
    git_branch = _git_rev_parse("--abbrev-ref HEAD")
    git_root = _git_rev_parse("--show-toplevel")
    key_env = [
        "FORCE_RUST_HIP",
        "RUST_HIP_USE_GPU_NBLIST_BUILDER",
        "CUDA_VISIBLE_DEVICES",
        "HIP_VISIBLE_DEVICES",
        "PYTHONHASHSEED",
    ]
    env_snapshot = {k: str(env.get(k, "")) for k in key_env}

    input_hashes: Dict[str, Dict[str, Any]] = {}
    for key in (
        "external_manifest",
        "strict_summary_json",
        "claim_policy_json",
        "active_learning_stage2_csv",
        "dashboard_compare_csv",
    ):
        src = str(resolved_inputs.get(key, "")).strip()
        if not src:
            continue
        info: Dict[str, Any] = {"path": src, "exists": bool(os.path.exists(src))}
        if os.path.exists(src):
            try:
                info["size_bytes"] = int(os.path.getsize(src))
            except Exception:
                pass
            info["sha256"] = _sha256_file(src)
        input_hashes[key] = info

    snapshot = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "date_tag": summary.get("date_tag"),
        "mode": summary.get("mode"),
        "targets": summary.get("targets"),
        "pass": bool(summary.get("pass", False)),
        "failed_step_index": summary.get("failed_step_index"),
        "python": {
            "version": sys.version,
            "executable": sys.executable,
        },
        "system": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "hostname": platform.node(),
        },
        "git": {
            "head": git_head or None,
            "branch": git_branch or None,
            "root": git_root or None,
        },
        "env": env_snapshot,
        "args": {
            "speed_mode": getattr(args, "speed_mode", ""),
            "speed_mode_replicas": getattr(args, "speed_mode_replicas", None),
            "speed_profile_max_replicas": getattr(args, "speed_profile_max_replicas", None),
            "rebench_use_ai_router": bool(getattr(args, "rebench_use_ai_router", True)),
            "rebench_ai_runtime_mode": getattr(args, "rebench_ai_runtime_mode", ""),
            "auto_select_rebench_ai_runtime_mode": bool(
                getattr(args, "auto_select_rebench_ai_runtime_mode", False)
            ),
            "rebench_ai_runtime_policy_json": getattr(args, "rebench_ai_runtime_policy_json", ""),
            "claim_profile_json": getattr(args, "claim_profile_json", ""),
            "feature_profile_json": getattr(args, "feature_profile_json", ""),
            "long_stability_gate_policy": getattr(args, "long_stability_gate_policy", ""),
            "commercial_readiness_enforce_pass": bool(getattr(args, "commercial_readiness_enforce_pass", False)),
            "commercial_readiness_min_score": getattr(args, "commercial_readiness_min_score", None),
            "commercial_readiness_min_external_targets": getattr(
                args, "commercial_readiness_min_external_targets", None
            ),
        },
        "resolved_inputs": resolved_inputs,
        "input_hashes": input_hashes,
    }

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False)
    return {"json": out_path, "git_head": git_head or None}


def _apply_claim_profile_json(args: argparse.Namespace) -> Dict[str, Any]:
    profile_path = _resolve_input_path(str(getattr(args, "claim_profile_json", "")).strip())
    payload = _read_json_if_exists(profile_path)
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


def _apply_feature_profile_json(args: argparse.Namespace) -> Dict[str, Any]:
    profile_path = _resolve_input_path(str(getattr(args, "feature_profile_json", "")).strip())
    payload = _read_json_if_exists(profile_path)
    if not payload:
        return {"path": profile_path, "loaded": False, "keys_applied": []}

    profile = payload.get("profile", payload) if isinstance(payload, dict) else {}
    if not isinstance(profile, dict):
        return {"path": profile_path, "loaded": False, "keys_applied": []}

    def _to_bool(v: Any) -> bool:
        if isinstance(v, bool):
            return v
        s = str(v).strip().lower()
        if s in {"1", "true", "yes", "on", "y"}:
            return True
        if s in {"0", "false", "no", "off", "n"}:
            return False
        return bool(v)

    field_casts = {
        "feature_enable_control_perturbation": _to_bool,
        "feature_control_perturbation_seed": int,
        "feature_perturb_ionic_strength_grid": str,
        "feature_perturb_ptm_count_grid": str,
        "feature_perturb_temperature_end_grid": str,
        "feature_perturb_hydro_scale_grid": str,
        "feature_perturb_force_scale_mult_grid": str,
        "feature_control_prefix": str,
        "feature_observed_prefix": str,
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


def _choose_rebench_ai_runtime_mode(
    *,
    args: argparse.Namespace,
    env: Dict[str, str],
    paths: Dict[str, str],
) -> Dict[str, Any]:
    requested_mode = str(getattr(args, "rebench_ai_runtime_mode", "scripted")).strip().lower()
    if requested_mode not in _VALID_AI_RUNTIME_MODES:
        requested_mode = "scripted"
    selected_mode = requested_mode

    policy_path = _resolve_input_path(str(getattr(args, "rebench_ai_runtime_policy_json", "")).strip())
    policy_payload = _read_json_if_exists(policy_path) if policy_path else {}
    default_policy_mode = str(policy_payload.get("default_runtime_mode", "")).strip().lower()
    fallback_order = policy_payload.get("selection_rule", {}).get("fallback_order", [])
    if not isinstance(fallback_order, list):
        fallback_order = []
    fallback_modes: List[str] = []
    for raw in [default_policy_mode, *fallback_order, "scripted", "eager"]:
        mode_i = str(raw).strip().lower()
        if mode_i in _VALID_AI_RUNTIME_MODES and mode_i not in fallback_modes:
            fallback_modes.append(mode_i)
    if not fallback_modes:
        fallback_modes = ["scripted", "eager"]

    status: Dict[str, Any] = {
        "enabled": bool(getattr(args, "auto_select_rebench_ai_runtime_mode", False)),
        "requested_mode": requested_mode,
        "selected_mode": selected_mode,
        "selection_source": "cli",
        "policy_json": policy_path,
        "policy_loaded": bool(policy_payload),
        "profile_json": str(paths.get("rebench_ai_runtime_profile_json", "")),
        "profile_csv": str(paths.get("rebench_ai_runtime_profile_csv", "")),
        "profile_status": {},
    }

    if not bool(getattr(args, "auto_select_rebench_ai_runtime_mode", False)):
        status["selected_mode"] = selected_mode
        return status

    if bool(getattr(args, "dry_run", False)):
        if selected_mode not in _VALID_AI_RUNTIME_MODES:
            selected_mode = fallback_modes[0]
        status["selected_mode"] = selected_mode
        status["selection_source"] = "dry_run_fallback"
        status["profile_status"] = {"ok": True, "dry_run": True}
        return status

    profile_targets = str(getattr(args, "rebench_ai_runtime_profile_targets", "")).strip() or str(args.targets)
    profile_cmd: List[str] = [
        sys.executable,
        "tools/profile_ai_runtime_modes.py",
        "--targets",
        profile_targets,
        "--modes",
        str(getattr(args, "rebench_ai_runtime_profile_modes", "eager,scripted,compiled,onnx")),
        "--steps",
        str(int(getattr(args, "rebench_ai_runtime_profile_steps", 80))),
        "--runs",
        str(int(getattr(args, "rebench_ai_runtime_profile_runs", 1))),
        "--warmup-steps",
        str(int(getattr(args, "rebench_ai_runtime_profile_warmup_steps", 30))),
        "--batch-replicas",
        str(int(getattr(args, "rebench_ai_runtime_profile_batch_replicas", 1))),
        "--ai-interval",
        str(int(getattr(args, "rebench_ai_runtime_profile_ai_interval", 4))),
        "--out-csv",
        str(paths["rebench_ai_runtime_profile_csv"]),
        "--out-json",
        str(paths["rebench_ai_runtime_profile_json"]),
    ]
    profile_ckpt = str(getattr(args, "rebench_ai_router_checkpoint", "")).strip()
    if profile_ckpt:
        profile_cmd.extend(["--ai-router-checkpoint", profile_ckpt])
        if bool(getattr(args, "rebench_ai_router_checkpoint_strict", False)):
            profile_cmd.append("--ai-router-checkpoint-strict")
    profile_status = _run_cmd(profile_cmd, env=env, dry_run=False)
    status["profile_status"] = profile_status

    best_mode = ""
    if bool(profile_status.get("ok", False)):
        profile_payload = _read_json_if_exists(str(paths["rebench_ai_runtime_profile_json"]))
        best_mode = str(profile_payload.get("summary", {}).get("best_mode", "")).strip().lower()
    if best_mode in _VALID_AI_RUNTIME_MODES:
        selected_mode = best_mode
        status["selection_source"] = "profile_best_mode"
    elif selected_mode not in _VALID_AI_RUNTIME_MODES:
        selected_mode = fallback_modes[0]
        status["selection_source"] = "policy_fallback"

    status["selected_mode"] = selected_mode
    return status


def _collect_claim_status(paths: Dict[str, str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}

    claim_initial = _read_json_if_exists(f"{paths['claim_prefix']}_summary.json")
    if claim_initial:
        summary = claim_initial.get("summary", {}) if isinstance(claim_initial.get("summary"), dict) else {}
        if "claim_ready_for_allatom" in summary:
            out["initial_claim_ready_for_allatom"] = bool(summary.get("claim_ready_for_allatom"))
        if "claim_failed_metrics" in summary:
            out["initial_claim_failed_metrics"] = int(summary.get("claim_failed_metrics", -1))

    claim_corrected = _read_json_if_exists(f"{paths['claim_correction_prefix']}_summary.json")
    if claim_corrected:
        summary = claim_corrected.get("summary", {}) if isinstance(claim_corrected.get("summary"), dict) else {}
        if "claim_ready_for_allatom" in summary:
            out["corrected_claim_ready_for_allatom"] = bool(summary.get("claim_ready_for_allatom"))
        if "claim_failed_metrics_after_runner" in summary:
            out["corrected_claim_failed_metrics"] = int(summary.get("claim_failed_metrics_after_runner", -1))
        if "improved" in summary:
            out["corrected_claim_improved"] = bool(summary.get("improved"))
        if "best_fail_count" in summary:
            out["corrected_best_fail_count"] = int(summary.get("best_fail_count", -1))

    return out


def _collect_long_stability_status(paths: Dict[str, str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}

    rebench_json = _read_json_if_exists(f"{paths['rebench_prefix']}_speed_accuracy.json")
    if rebench_json:
        summary = (
            rebench_json.get("long_stability_summary", {})
            if isinstance(rebench_json.get("long_stability_summary"), dict)
            else {}
        )
        if "gate_pass" in summary:
            out["baseline_gate_pass"] = bool(summary.get("gate_pass"))
        if "failed_targets" in summary and isinstance(summary.get("failed_targets"), list):
            out["baseline_failed_targets"] = [str(x) for x in summary.get("failed_targets", [])]

    tuned_json = _read_json_if_exists(str(paths.get("tuned_stability_json", "")))
    if tuned_json:
        summary = tuned_json.get("summary", {}) if isinstance(tuned_json.get("summary"), dict) else {}
        targets = int(summary.get("targets", 0) or 0)
        passed_targets = int(summary.get("passed_targets", 0) or 0)
        failed_targets = summary.get("failed_targets", [])
        if not isinstance(failed_targets, list):
            failed_targets = []
        tuned_gate_pass = bool(targets > 0 and passed_targets >= targets and len(failed_targets) == 0)
        out["tuned_targets"] = targets
        out["tuned_passed_targets"] = passed_targets
        out["tuned_failed_targets"] = [str(x) for x in failed_targets]
        out["tuned_gate_pass"] = tuned_gate_pass

    return out


def _collect_ood_status(paths: Dict[str, str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    payload = _read_json_if_exists(str(paths.get("ood_summary_json", "")))
    if not payload:
        return out
    out["pass"] = bool(payload.get("pass", False))
    pair_metrics = payload.get("pair_metrics", {}) if isinstance(payload.get("pair_metrics"), dict) else {}
    out["paired_targets"] = int(pair_metrics.get("paired_targets", 0) or 0)
    out["avg_pair_rmsd_aligned_A"] = pair_metrics.get("avg_pair_rmsd_aligned_A")
    out["real_pair_coverage"] = pair_metrics.get("real_pair_coverage")
    out["domain_coverage"] = pair_metrics.get("domain_coverage")
    out["covered_domains"] = pair_metrics.get("covered_domains")
    gates = payload.get("gates", {}) if isinstance(payload.get("gates"), dict) else {}
    min_pairs = gates.get("min_pairs", {}) if isinstance(gates.get("min_pairs"), dict) else {}
    if min_pairs:
        out["min_pairs_threshold_requested"] = min_pairs.get("threshold_requested")
        out["min_pairs_threshold_effective"] = min_pairs.get("threshold_effective")
    max_rmsd = gates.get("max_mean_pair_rmsd", {}) if isinstance(gates.get("max_mean_pair_rmsd"), dict) else {}
    if max_rmsd:
        out["max_mean_pair_rmsd_threshold"] = max_rmsd.get("threshold")
    proxy_summary = payload.get("proxy_summary", {}) if isinstance(payload.get("proxy_summary"), dict) else {}
    if proxy_summary:
        out["proxy_rows_added"] = int(proxy_summary.get("proxy_rows_added", 0) or 0)
        out["proxy_targets_added"] = proxy_summary.get("proxy_targets_added", [])
    return out


def _build_ood_dual_report_payload(
    *,
    baseline_payload: Dict[str, Any],
    robust_payload: Dict[str, Any],
) -> Dict[str, Any]:
    baseline_pair = (
        baseline_payload.get("pair_metrics", {})
        if isinstance(baseline_payload.get("pair_metrics"), dict)
        else {}
    )
    robust_pair = (
        robust_payload.get("pair_metrics", {})
        if isinstance(robust_payload.get("pair_metrics"), dict)
        else {}
    )
    baseline_artifacts = (
        baseline_payload.get("artifacts", {})
        if isinstance(baseline_payload.get("artifacts"), dict)
        else {}
    )
    robust_artifacts = (
        robust_payload.get("artifacts", {})
        if isinstance(robust_payload.get("artifacts"), dict)
        else {}
    )
    baseline_pair_csv = str(baseline_artifacts.get("pair_csv", "")).strip()
    robust_pair_csv = str(robust_artifacts.get("pair_csv", "")).strip()
    baseline_pair_sha = _sha256_file(baseline_pair_csv)
    robust_pair_sha = _sha256_file(robust_pair_csv)

    baseline_avg = _safe_float(baseline_pair.get("avg_pair_rmsd_aligned_A"))
    robust_avg = _safe_float(robust_pair.get("avg_pair_rmsd_aligned_A"))
    delta_avg = None
    if baseline_avg is not None and robust_avg is not None:
        delta_avg = float(robust_avg - baseline_avg)

    baseline_paired = int(baseline_pair.get("paired_targets", 0) or 0)
    robust_paired = int(robust_pair.get("paired_targets", 0) or 0)
    baseline_proxy = int(baseline_payload.get("proxy_summary", {}).get("proxy_rows_added", 0) or 0)
    robust_proxy = int(robust_payload.get("proxy_summary", {}).get("proxy_rows_added", 0) or 0)
    baseline_windowed = int(baseline_pair.get("windowed_matches", 0) or 0)
    robust_windowed = int(robust_pair.get("windowed_matches", 0) or 0)

    comparison = {
        "avg_pair_rmsd_aligned_A_delta": delta_avg,
        "paired_targets_delta": int(robust_paired - baseline_paired),
        "proxy_rows_added_delta": int(robust_proxy - baseline_proxy),
        "windowed_matches_delta": int(robust_windowed - baseline_windowed),
        "pair_csv_hash_identical": bool(
            baseline_pair_sha is not None
            and robust_pair_sha is not None
            and str(baseline_pair_sha) == str(robust_pair_sha)
        ),
    }
    interpretation = "stable_under_robust_probe"
    if robust_avg is None or robust_paired <= 0:
        interpretation = "robust_probe_insufficient_pairs"
    elif delta_avg is not None and delta_avg > 0.75:
        interpretation = "robust_probe_degradation_detected"
    elif robust_paired < baseline_paired:
        interpretation = "robust_probe_pair_coverage_drop"

    return {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "summary": {
            "pass": bool(
                bool(baseline_payload.get("pass", False))
                and bool(robust_payload.get("pass", False))
            ),
            "interpretation": interpretation,
        },
        "baseline": {
            "pass": bool(baseline_payload.get("pass", False)),
            "paired_targets": baseline_paired,
            "avg_pair_rmsd_aligned_A": baseline_avg,
            "proxy_rows_added": baseline_proxy,
            "windowed_matches": baseline_windowed,
            "pair_csv": baseline_pair_csv,
            "pair_csv_sha256": baseline_pair_sha,
            "summary_json": str(baseline_artifacts.get("summary_json", "")).strip(),
        },
        "robustness_probe": {
            "pass": bool(robust_payload.get("pass", False)),
            "paired_targets": robust_paired,
            "avg_pair_rmsd_aligned_A": robust_avg,
            "proxy_rows_added": robust_proxy,
            "windowed_matches": robust_windowed,
            "pair_csv": robust_pair_csv,
            "pair_csv_sha256": robust_pair_sha,
            "summary_json": str(robust_artifacts.get("summary_json", "")).strip(),
        },
        "comparison": comparison,
    }


def _write_ood_dual_report(
    *,
    out_json: str,
    out_md: str,
    payload: Dict[str, Any],
) -> None:
    os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(out_md) or ".", exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    baseline = payload.get("baseline", {}) if isinstance(payload.get("baseline"), dict) else {}
    robust = payload.get("robustness_probe", {}) if isinstance(payload.get("robustness_probe"), dict) else {}
    cmpv = payload.get("comparison", {}) if isinstance(payload.get("comparison"), dict) else {}
    summary = payload.get("summary", {}) if isinstance(payload.get("summary"), dict) else {}
    lines = [
        "# OOD Dual Report",
        "",
        f"- pass: {summary.get('pass')}",
        f"- interpretation: {summary.get('interpretation')}",
        "",
        "## Baseline",
        f"- pass: {baseline.get('pass')}",
        f"- paired_targets: {baseline.get('paired_targets')}",
        f"- avg_pair_rmsd_aligned_A: {baseline.get('avg_pair_rmsd_aligned_A')}",
        f"- proxy_rows_added: {baseline.get('proxy_rows_added')}",
        f"- windowed_matches: {baseline.get('windowed_matches')}",
        f"- pair_csv: {baseline.get('pair_csv')}",
        f"- pair_csv_sha256: {baseline.get('pair_csv_sha256')}",
        "",
        "## Robustness Probe",
        f"- pass: {robust.get('pass')}",
        f"- paired_targets: {robust.get('paired_targets')}",
        f"- avg_pair_rmsd_aligned_A: {robust.get('avg_pair_rmsd_aligned_A')}",
        f"- proxy_rows_added: {robust.get('proxy_rows_added')}",
        f"- windowed_matches: {robust.get('windowed_matches')}",
        f"- pair_csv: {robust.get('pair_csv')}",
        f"- pair_csv_sha256: {robust.get('pair_csv_sha256')}",
        "",
        "## Comparison",
        f"- avg_pair_rmsd_aligned_A_delta: {cmpv.get('avg_pair_rmsd_aligned_A_delta')}",
        f"- paired_targets_delta: {cmpv.get('paired_targets_delta')}",
        f"- proxy_rows_added_delta: {cmpv.get('proxy_rows_added_delta')}",
        f"- windowed_matches_delta: {cmpv.get('windowed_matches_delta')}",
        f"- pair_csv_hash_identical: {cmpv.get('pair_csv_hash_identical')}",
    ]
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def _run_ood_dual_report(
    args: argparse.Namespace,
    *,
    paths: Dict[str, str],
    env: Dict[str, str],
    date_tag: str,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"requested": bool(getattr(args, "run_ood_dual_report", True))}
    if not bool(getattr(args, "run_ood_dual_report", True)):
        return payload
    if not bool(getattr(args, "run_ood_gate", True)):
        payload.update({"ok": True, "skipped": "run_ood_gate_disabled"})
        return payload
    if bool(getattr(args, "dry_run", False)):
        payload.update(
            {
                "dry_run": True,
                "ok": True,
                "out_json": paths.get("ood_dual_report_json"),
                "out_md": paths.get("ood_dual_report_md"),
                "robust_summary_json": paths.get("ood_robust_summary_json"),
            }
        )
        return payload

    baseline_summary_json = str(paths.get("ood_summary_json", "")).strip()
    baseline_curated_csv = f"{paths.get('ood_prefix', '')}_curated.csv"
    baseline_curated_json = f"{paths.get('ood_prefix', '')}_curated.json"
    robust_prefix = str(paths.get("ood_robust_prefix", "")).strip()
    robust_out_dir = str(args.public_out_dir).rstrip("/") + f"/{date_tag}_ood_robust"
    robust_cmd: List[str] = [
        sys.executable,
        "tools/run_ood_first_validation_batch.py",
        "--targets",
        str(args.targets),
        "--date-tag",
        f"{date_tag}-robust",
        "--sources-csv",
        str(args.sources_csv),
        "--out-dir",
        robust_out_dir,
        "--out-prefix",
        robust_prefix,
        "--manifest-csv",
        str(paths.get("fetch_manifest", "")),
        "--curated-csv",
        str(baseline_curated_csv),
        "--curated-json",
        str(baseline_curated_json),
        "--skip-fetch",
        "--skip-curation",
        "--min-pairs",
        str(int(getattr(args, "ood_min_pairs", 8))),
        "--max-mean-pair-rmsd",
        str(float(getattr(args, "ood_robust_max_mean_pair_rmsd", 6.0))),
        "--max-length-ratio",
        str(float(getattr(args, "ood_max_length_ratio", 1.5))),
        "--max-windowed-rmsd",
        str(float(getattr(args, "ood_robust_max_windowed_rmsd", 8.0))),
        "--max-proxy-rows",
        str(int(getattr(args, "ood_max_proxy_rows", 0))),
    ]
    if bool(getattr(args, "ood_require_real_afdb", True)):
        robust_cmd.append("--require-real-afdb")
    if bool(getattr(args, "ood_robust_enable_proxy_manifest", False)):
        robust_cmd.append("--enable-proxy-manifest")
    else:
        robust_cmd.append("--no-enable-proxy-manifest")
    if bool(getattr(args, "ood_robust_enable_windowed_match", False)):
        robust_cmd.append("--enable-windowed-match")
    else:
        robust_cmd.append("--no-enable-windowed-match")
    if bool(getattr(args, "ood_robust_strict_fail", False)):
        robust_cmd.append("--strict-fail")

    rec = _run_cmd(robust_cmd, env=env, dry_run=False)
    raw_rc = rec.get("returncode", None)
    try:
        rc = int(raw_rc) if raw_rc is not None else 1
    except Exception:
        rc = 1
    robust_ok = bool(rec.get("ok", False))

    baseline_payload = _read_json_if_exists(baseline_summary_json)
    robust_payload = _read_json_if_exists(str(paths.get("ood_robust_summary_json", "")))
    report_payload = _build_ood_dual_report_payload(
        baseline_payload=baseline_payload,
        robust_payload=robust_payload,
    )
    _write_ood_dual_report(
        out_json=str(paths.get("ood_dual_report_json", "")),
        out_md=str(paths.get("ood_dual_report_md", "")),
        payload=report_payload,
    )

    enforce = bool(getattr(args, "ood_dual_report_enforce_pass", False))
    dual_pass = bool(report_payload.get("summary", {}).get("pass", False))
    ok = bool(robust_ok and ((not enforce) or dual_pass))
    payload.update(
        {
            "ok": ok,
            "returncode": int(rc),
            "cmd_str": rec.get("cmd_str"),
            "stdout_tail": rec.get("stdout_tail", ""),
            "stderr_tail": rec.get("stderr_tail", ""),
            "out_json": paths.get("ood_dual_report_json"),
            "out_md": paths.get("ood_dual_report_md"),
            "robust_summary_json": paths.get("ood_robust_summary_json"),
            "dual_pass": dual_pass,
            "enforce": enforce,
            "gate_failure": ("ood_dual_report_enforce_pass_failed" if (enforce and not dual_pass) else ""),
        }
    )
    return payload


def _collect_active_learning_status(paths: Dict[str, str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    payload = _read_json_if_exists(str(paths.get("active_learning_summary_json", "")))
    if not payload:
        return out
    out["pass"] = bool(payload.get("pass", False))
    summary = payload.get("summary", {}) if isinstance(payload.get("summary"), dict) else {}
    if summary:
        out["hard_mining_selected_targets_count"] = summary.get("hard_mining_selected_targets_count")
        out["hard_mining_selected_targets"] = summary.get("hard_mining_selected_targets")
        out["curriculum_executed"] = summary.get("curriculum_executed")
        out["curriculum_pass"] = summary.get("curriculum_pass")
        out["claim_executed"] = summary.get("claim_executed")
        out["claim_pass"] = summary.get("claim_pass")
        out["claim_ready_for_allatom"] = summary.get("claim_ready_for_allatom")
    return out


def _collect_live_unseen_hardcase_status(paths: Dict[str, str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    payload = _read_json_if_exists(str(paths.get("active_learning_live_unseen_hardcase_summary_json", "")))
    if not payload:
        return out
    out["pass"] = bool(payload.get("pass", False))
    out["rows_total"] = int(payload.get("rows_total", 0) or 0)
    out["selected_targets_count"] = int(payload.get("selected_targets_count", 0) or 0)
    out["selected_targets"] = payload.get("selected_targets", []) if isinstance(payload.get("selected_targets"), list) else []
    out["used_fallback_all_targets"] = bool(payload.get("used_fallback_all_targets", False))
    out["out_manifest_csv"] = payload.get("out_manifest_csv")
    return out


def _collect_active_learning_priority_status(paths: Dict[str, str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    payload = _read_json_if_exists(str(paths.get("active_learning_priority_json", "")))
    if not payload:
        return out
    out["priority_targets_count"] = int(
        payload.get("summary", {}).get("priority_targets_count", 0)
        if isinstance(payload.get("summary"), dict)
        else 0
    )
    out["ood_selected"] = int(
        payload.get("summary", {}).get("ood_selected", 0) if isinstance(payload.get("summary"), dict) else 0
    )
    out["oversize_selected"] = int(
        payload.get("summary", {}).get("oversize_selected", 0) if isinstance(payload.get("summary"), dict) else 0
    )
    out["feature_selected"] = int(
        payload.get("summary", {}).get("feature_selected", 0) if isinstance(payload.get("summary"), dict) else 0
    )
    return out


def _collect_active_learning_priority_ab_status(paths: Dict[str, str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    payload = _read_json_if_exists(str(paths.get("active_learning_priority_ab_json", "")))
    if not payload:
        return out
    summary = payload.get("summary", {}) if isinstance(payload.get("summary"), dict) else {}
    out["baseline_count"] = int(summary.get("baseline_count", 0) or 0)
    out["candidate_count"] = int(summary.get("candidate_count", 0) or 0)
    out["jaccard"] = _safe_float(summary.get("jaccard"))
    out["added_in_candidate_count"] = int(summary.get("added_in_candidate_count", 0) or 0)
    out["ood_coverage_baseline"] = _safe_float(summary.get("ood_coverage_baseline"))
    out["ood_coverage_candidate"] = _safe_float(summary.get("ood_coverage_candidate"))
    out["ood_coverage_delta"] = _safe_float(summary.get("ood_coverage_delta"))
    return out


def _collect_dashboard_status(paths: Dict[str, str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    payload = _read_json_if_exists(str(paths.get("dashboard_json", "")))
    if not payload:
        return out
    out["title"] = payload.get("title")
    metrics = payload.get("metrics", [])
    runs = payload.get("runs", [])
    pdb_entries = payload.get("pdb_entries", [])
    out["metrics_count"] = int(len(metrics)) if isinstance(metrics, list) else 0
    out["run_count"] = int(len(runs)) if isinstance(runs, list) else 0
    out["pdb_count"] = int(len(pdb_entries)) if isinstance(pdb_entries, list) else 0
    out["target_filters"] = payload.get("target_filters", [])
    return out


def _collect_commercial_readiness_status(paths: Dict[str, str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    payload = _read_json_if_exists(str(paths.get("commercial_readiness_json", "")))
    if not payload:
        return out
    summary = payload.get("summary", {}) if isinstance(payload.get("summary"), dict) else {}
    out["readiness_score"] = summary.get("readiness_score")
    out["readiness_tier"] = summary.get("readiness_tier")
    out["considered_checks"] = summary.get("considered_checks")
    out["passed_checks"] = summary.get("passed_checks")
    out["failed_checks"] = summary.get("failed_checks")
    out["critical_checks_pass"] = summary.get("critical_checks_pass")
    out["recommendations_count"] = (
        len(payload.get("recommendations", []))
        if isinstance(payload.get("recommendations"), list)
        else 0
    )
    return out


def _targets_to_dashboard_filters(targets: str) -> List[str]:
    token = str(targets).strip()
    if (not token) or (token.lower() in {"all", "noncyclic", "sources_all"}):
        return []
    out: List[str] = []
    seen = set()
    for part in token.split(","):
        item = str(part).strip()
        if not item:
            continue
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _collect_special_case_status(paths: Dict[str, str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    payload = _read_json_if_exists(str(paths.get("special_case_summary_json", "")))
    if not payload:
        return out
    out["pass"] = bool(payload.get("pass", False))
    raw_exit = payload.get("exit_code", None)
    if raw_exit is None:
        out["exit_code"] = None
    else:
        try:
            out["exit_code"] = int(raw_exit)
        except Exception:
            out["exit_code"] = None
    out["failed_stage"] = payload.get("failed_stage")
    stages = payload.get("stages", {}) if isinstance(payload.get("stages"), dict) else {}
    stage_pass = {}
    for stage_name in ("stage_metal", "stage_dna", "stage_membrane"):
        item = stages.get(stage_name, {}) if isinstance(stages.get(stage_name), dict) else {}
        if item:
            stage_pass[stage_name] = bool(item.get("pass", False))
    if stage_pass:
        out["stage_pass"] = stage_pass
    return out


def _classify_failure_reason(summary: Dict[str, Any], failed_step: Dict[str, Any]) -> Dict[str, str]:
    if bool(summary.get("initial_claim_requirement_failed", False)):
        return {
            "reason_code": "claim_initial_not_ready",
            "reason_hint": "claim 입력(thermo/kinetics/experiment) 품질과 정책 임계값을 우선 점검하세요.",
        }
    if bool(summary.get("measured_proxy_requirement_failed", False)):
        return {
            "reason_code": "measured_proxy_rows_detected",
            "reason_hint": "measured OOD 실행에서 proxy rows가 섞였습니다. sources/tags CSV를 재검증하세요.",
        }
    if bool(summary.get("dashboard_metrics_requirement_failed", False)):
        return {
            "reason_code": "dashboard_metrics_empty",
            "reason_hint": "feature CSV 컬럼/타깃필터를 확인해 dashboard metrics_count를 1 이상으로 맞추세요.",
        }

    post_failures = summary.get("post_process_failures", [])
    if isinstance(post_failures, list) and post_failures:
        f0 = post_failures[0] if isinstance(post_failures[0], dict) else {}
        reason = str(f0.get("reason", "")).strip()
        if reason == "packet_build_failed":
            return {
                "reason_code": "external_packet_build_failed",
                "reason_hint": "external packet 입력 경로(gate/parity/stage2/fidelity/dashboard)를 우선 점검하세요.",
            }
        if reason == "commercial_readiness_report_failed":
            return {
                "reason_code": "commercial_readiness_gate_failed",
                "reason_hint": "commercial_readiness 실패 체크를 확인하고 external targets/꼬리지표를 보정하세요.",
            }
        if reason == "submission_publish_failed":
            return {
                "reason_code": "external_submission_publish_failed",
                "reason_hint": "external submission 필수 파일(batch summary/dashboard/external packet) 누락을 해결하세요.",
            }

    gate_failure = str(failed_step.get("gate_failure", "")).strip()
    if gate_failure:
        return {
            "reason_code": f"gate_{gate_failure}",
            "reason_hint": "게이트 실패 원인 항목의 입력/정책 임계값을 확인하세요.",
        }

    step_name = str(failed_step.get("name", "")).strip()
    if step_name:
        return {
            "reason_code": f"step_{step_name}_failed",
            "reason_hint": "해당 단계 stderr/stdout tail을 확인해 입력/런타임 오류를 수정하세요.",
        }
    return {
        "reason_code": "unknown_failure",
        "reason_hint": "nightly_failure_latest의 stderr/stdout tail을 확인하세요.",
    }


def _write_failure_latest_report(summary: Dict[str, Any], paths: Dict[str, str]) -> Dict[str, Any]:
    failed_step: Dict[str, Any] = {}
    for rec in summary.get("results", []):
        if not bool(rec.get("ok", False)):
            failed_step = rec
            break
    reason = _classify_failure_reason(summary, failed_step)
    payload = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "date_tag": summary.get("date_tag"),
        "mode": summary.get("mode"),
        "pass": bool(summary.get("pass", False)),
        "failed_step_index": summary.get("failed_step_index"),
        "failed_step_name": failed_step.get("name"),
        "failed_cmd": failed_step.get("cmd_str"),
        "failed_returncode": failed_step.get("returncode"),
        "failed_gate": failed_step.get("gate_failure"),
        "reason_code": reason.get("reason_code"),
        "reason_hint": reason.get("reason_hint"),
        "stderr_tail": failed_step.get("stderr_tail", ""),
        "stdout_tail": failed_step.get("stdout_tail", ""),
        "claim_status": summary.get("claim_status", {}),
        "ood_status": summary.get("ood_status", {}),
        "ood_measured20_status": summary.get("ood_measured20_status", {}),
        "ood_measured40_status": summary.get("ood_measured40_status", {}),
        "active_learning_live_unseen_hardcase_status": summary.get("active_learning_live_unseen_hardcase_status", {}),
        "special_case_status": summary.get("special_case_status", {}),
        "commercial_readiness_status": summary.get("commercial_readiness_status", {}),
    }
    out_json = str(paths.get("failure_latest_json", "")).strip()
    out_md = str(paths.get("failure_latest_md", "")).strip()
    if out_json:
        os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
    if out_md:
        os.makedirs(os.path.dirname(out_md) or ".", exist_ok=True)
        lines = [
            "# Nightly Failure Latest",
            "",
            f"- generated_at: {payload['generated_at_local']}",
            f"- date_tag: {payload['date_tag']}",
            f"- mode: {payload['mode']}",
            f"- pass: {payload['pass']}",
            f"- failed_step_index: {payload['failed_step_index']}",
            f"- failed_step_name: {payload['failed_step_name']}",
            f"- failed_returncode: {payload['failed_returncode']}",
            f"- failed_gate: {payload['failed_gate']}",
            f"- reason_code: {payload.get('reason_code')}",
            f"- reason_hint: {payload.get('reason_hint')}",
            "",
            "## Failed Command",
            f"`{payload['failed_cmd']}`",
            "",
            "## stderr_tail",
            "```text",
            str(payload.get("stderr_tail", "")),
            "```",
            "",
            "## stdout_tail",
            "```text",
            str(payload.get("stdout_tail", "")),
            "```",
        ]
        with open(out_md, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    return {"json": out_json, "md": out_md}


def _run_runs_maintenance(args: argparse.Namespace, paths: Dict[str, str]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    if not bool(getattr(args, "maintenance_prune_runs", False)):
        return payload
    try:
        from tools.prune_runs_files import prune_runs_files

        protected = list(getattr(args, "maintenance_protect_prefix", []) or [])
        # Keep current run artifacts pinned by date-tag prefix.
        date_tag = str(getattr(args, "date_tag", "") or "").strip()
        if date_tag:
            protected.append(f"nightly_screening_batch_{date_tag}")
            protected.append(f"ood_measured20_validation_batch_nightly_{date_tag}")
            protected.append(f"ood_measured40_validation_batch_nightly_{date_tag}")
            protected.append(f"active_learning_cycle_nightly_{date_tag}")
        prune_payload = prune_runs_files(
            runs_dir=str(args.runs_dir),
            keep_per_role=int(getattr(args, "maintenance_keep_per_role", 2)),
            exts=[".csv", ".json"],
            protect_prefixes=protected,
            dry_run=bool(args.dry_run),
            archive_root=str(getattr(args, "maintenance_archive_root", "_archive_pruned")),
        )
        payload["prune"] = prune_payload

        moved_files = int(prune_payload.get("moved_files", 0) or 0)
        archive_dir = str(prune_payload.get("archive_dir", "")).strip()
        if (
            bool(getattr(args, "maintenance_compress_archive", True))
            and (not bool(args.dry_run))
            and moved_files > 0
            and archive_dir
            and os.path.isdir(archive_dir)
        ):
            tar_path = shutil.make_archive(archive_dir, "gztar", root_dir=archive_dir)
            payload["archive_tar_gz"] = tar_path
            if bool(getattr(args, "maintenance_remove_uncompressed_archive", True)):
                shutil.rmtree(archive_dir, ignore_errors=True)
                payload["archive_uncompressed_removed"] = True
            else:
                payload["archive_uncompressed_removed"] = False
    except Exception as exc:
        payload["error"] = str(exc)

    out_json = str(paths.get("maintenance_summary_json", "")).strip()
    if out_json:
        os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
    return payload


def _run_external_packet(
    args: argparse.Namespace,
    *,
    paths: Dict[str, str],
    env: Dict[str, str],
    external_packet_accuracy_external_csv_path: str = "",
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"requested": bool(getattr(args, "run_external_packet", True))}
    if not bool(getattr(args, "run_external_packet", True)):
        return payload
    if bool(getattr(args, "dry_run", False)):
        payload.update({"dry_run": True, "ok": True, "out_json": paths.get("external_packet_json")})
        return payload

    gate_json = _resolve_input_path(str(getattr(args, "external_packet_gate_json", "")).strip())
    parity_csv = _resolve_input_path(str(getattr(args, "external_packet_parity_target_csv", "")).strip())
    stage2_csv = _resolve_input_path(str(getattr(args, "external_packet_stage2_csv", "")).strip())
    fidelity_csv = _resolve_input_path(str(getattr(args, "external_packet_fidelity_csv", "")).strip())
    strict_summary_json = _resolve_input_path(str(getattr(args, "strict_summary_json", "")).strip())

    cmd: List[str] = [
        sys.executable,
        "tools/build_external_eval_packet.py",
        "--packet-version",
        str(getattr(args, "external_packet_version", "v3")),
        "--gate-json",
        str(gate_json),
        "--parity-target-csv",
        str(parity_csv),
        "--stage2-csv",
        str(stage2_csv),
        "--fidelity-csv",
        str(fidelity_csv),
        "--feature-csv",
        str(paths.get("feature_csv", "")),
        "--strict-release-summary-json",
        str(strict_summary_json),
        "--nightly-summary-json",
        str(paths.get("batch_summary_json", "")),
        "--claim-correction-summary-json",
        f"{paths.get('claim_correction_prefix','')}_summary.json",
        "--dashboard-json",
        str(paths.get("dashboard_json", "")),
        "--dashboard-html",
        str(paths.get("dashboard_html", "")),
        "--out-json",
        str(paths.get("external_packet_json", "")),
    ]
    if bool(getattr(args, "external_packet_strict_optional_sources", True)):
        cmd.append("--strict-optional-sources")

    accuracy_external_csv = (
        _resolve_input_path(str(external_packet_accuracy_external_csv_path).strip())
        or _resolve_input_path(str(getattr(args, "external_packet_accuracy_external_csv", "")).strip())
        or _resolve_input_path(str(getattr(args, "accuracy_external_csv", "")).strip())
    )
    if accuracy_external_csv:
        cmd.extend(["--accuracy-external-csv", str(accuracy_external_csv)])

    quality_curation_csv = _resolve_input_path(str(getattr(args, "external_packet_quality_curation_csv", "")).strip())
    if quality_curation_csv:
        cmd.extend(["--quality-curation-csv", str(quality_curation_csv)])

    reproducibility_json = _resolve_input_path(str(getattr(args, "external_packet_reproducibility_json", "")).strip())
    if reproducibility_json:
        cmd.extend(["--reproducibility-json", str(reproducibility_json)])

    baseline_config_json = _resolve_input_path(str(getattr(args, "external_packet_baseline_config_json", "")).strip())
    if baseline_config_json:
        cmd.extend(["--baseline-config-json", str(baseline_config_json)])

    rec = _run_cmd(cmd, env=env, dry_run=False)
    raw_rc = rec.get("returncode", None)
    try:
        rc = int(raw_rc) if raw_rc is not None else 1
    except Exception:
        rc = 1
    payload.update(
        {
            "ok": bool(rec.get("ok", False)),
            "returncode": int(rc),
            "cmd_str": rec.get("cmd_str"),
            "stdout_tail": rec.get("stdout_tail", ""),
            "stderr_tail": rec.get("stderr_tail", ""),
            "out_json": paths.get("external_packet_json"),
        }
    )
    return payload


def _run_commercial_readiness(
    args: argparse.Namespace,
    *,
    paths: Dict[str, str],
    env: Dict[str, str],
    external_packet_accuracy_external_csv_path: str = "",
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "requested": bool(getattr(args, "run_commercial_readiness", True)),
    }
    if not bool(getattr(args, "run_commercial_readiness", True)):
        return payload
    if bool(getattr(args, "dry_run", False)):
        payload.update(
            {
                "dry_run": True,
                "ok": True,
                "out_json": paths.get("commercial_readiness_json"),
                "out_csv": paths.get("commercial_readiness_csv"),
                "out_md": paths.get("commercial_readiness_md"),
            }
        )
        return payload

    nightly_summary_json = _resolve_input_path(
        str(getattr(args, "commercial_readiness_nightly_summary_json", "")).strip()
    ) or str(paths.get("batch_summary_json", ""))
    strict_summary_json = _resolve_input_path(
        str(getattr(args, "commercial_readiness_strict_summary_json", "")).strip()
    ) or _resolve_input_path(str(getattr(args, "strict_summary_json", "")).strip())
    dashboard_json = _resolve_input_path(
        str(getattr(args, "commercial_readiness_dashboard_json", "")).strip()
    ) or str(paths.get("dashboard_json", ""))
    external_packet_json = _resolve_input_path(
        str(getattr(args, "commercial_readiness_external_packet_json", "")).strip()
    ) or str(paths.get("external_packet_json", ""))

    cmd: List[str] = [
        sys.executable,
        "tools/build_commercial_readiness_report.py",
        "--nightly-summary-json",
        str(nightly_summary_json),
        "--strict-release-summary-json",
        str(strict_summary_json),
        "--dashboard-json",
        str(dashboard_json),
        "--external-packet-json",
        str(external_packet_json),
        "--stage2-csv",
        str(
            _resolve_input_path(str(getattr(args, "commercial_readiness_stage2_csv", "")).strip())
            or _resolve_input_path(f"{paths.get('rebench_prefix','')}_stage2.csv")
        ),
        "--trajectory-target-tail-csv",
        str(_resolve_input_path(str(getattr(args, "commercial_readiness_trajectory_target_tail_csv", "")).strip())),
        "--accuracy-external-csv",
        str(
            _resolve_input_path(str(getattr(args, "commercial_readiness_accuracy_external_csv", "")).strip())
            or _resolve_input_path(str(external_packet_accuracy_external_csv_path).strip())
            or _resolve_input_path(str(getattr(args, "external_packet_accuracy_external_csv", "")).strip())
            or _resolve_input_path(str(getattr(args, "accuracy_external_csv", "")).strip())
        ),
        "--feature-csv",
        str(
            _resolve_input_path(str(getattr(args, "commercial_readiness_feature_csv", "")).strip())
            or _resolve_input_path(str(paths.get("feature_csv", "")).strip())
        ),
        "--strict-source-policy",
        str(getattr(args, "commercial_readiness_strict_source_policy", "full_only")),
        "--speedup-threshold",
        str(float(getattr(args, "commercial_readiness_speedup_threshold", 12.0))),
        "--speedup-p95-threshold",
        str(float(getattr(args, "commercial_readiness_speedup_p95_threshold", 12.0))),
        "--speedup-worst-threshold",
        str(float(getattr(args, "commercial_readiness_speedup_worst_threshold", 12.0))),
        "--max-rmsd-p95-a",
        str(float(getattr(args, "commercial_readiness_max_rmsd_p95_a", 8.0))),
        "--max-rmsd-worst-a",
        str(float(getattr(args, "commercial_readiness_max_rmsd_worst_a", 12.0))),
        "--min-dashboard-metrics",
        str(int(getattr(args, "commercial_readiness_min_dashboard_metrics", 3))),
        "--min-dashboard-runs",
        str(int(getattr(args, "commercial_readiness_min_dashboard_runs", 1))),
        "--min-external-targets",
        str(int(getattr(args, "commercial_readiness_min_external_targets", 5))),
        "--min-feature-targets",
        str(int(getattr(args, "commercial_readiness_min_feature_targets", 8))),
        "--feature-max-missing-rate",
        str(float(getattr(args, "commercial_readiness_feature_max_missing_rate", 0.15))),
        "--feature-min-variable-cols",
        str(int(getattr(args, "commercial_readiness_feature_min_variable_cols", 8))),
        "--feature-max-constant-flag-cols",
        str(int(getattr(args, "commercial_readiness_feature_max_constant_flag_cols", 8))),
        "--out-json",
        str(paths.get("commercial_readiness_json", "")),
        "--out-csv",
        str(paths.get("commercial_readiness_csv", "")),
        "--out-md",
        str(paths.get("commercial_readiness_md", "")),
    ]
    traj_p05_th = getattr(args, "commercial_readiness_traj_fps_p05_threshold", None)
    if traj_p05_th is not None:
        cmd.extend(["--traj-fps-p05-threshold", str(float(traj_p05_th))])
    traj_worst_th = getattr(args, "commercial_readiness_traj_fps_worst_threshold", None)
    if traj_worst_th is not None:
        cmd.extend(["--traj-fps-worst-threshold", str(float(traj_worst_th))])
    if bool(getattr(args, "commercial_readiness_disable_auto_discovery", False)):
        cmd.append("--disable-auto-discovery")

    rec = _run_cmd(cmd, env=env, dry_run=False)
    raw_rc = rec.get("returncode", None)
    try:
        rc = int(raw_rc) if raw_rc is not None else 1
    except Exception:
        rc = 1
    payload.update(
        {
            "ok": bool(rec.get("ok", False)),
            "returncode": int(rc),
            "cmd_str": rec.get("cmd_str"),
            "stdout_tail": rec.get("stdout_tail", ""),
            "stderr_tail": rec.get("stderr_tail", ""),
            "out_json": paths.get("commercial_readiness_json"),
            "out_csv": paths.get("commercial_readiness_csv"),
            "out_md": paths.get("commercial_readiness_md"),
        }
    )
    report = _read_json_if_exists(str(paths.get("commercial_readiness_json", "")))
    if report:
        summary = report.get("summary", {}) if isinstance(report.get("summary"), dict) else {}
        score = summary.get("readiness_score")
        failed_checks = summary.get("failed_checks")
        critical_checks_pass = bool(summary.get("critical_checks_pass", False))
        payload["readiness_summary"] = summary
        payload["report_pass"] = None
        try:
            min_score = float(getattr(args, "commercial_readiness_min_score", 75.0))
            score_ok = (score is not None) and (float(score) >= float(min_score))
            failed_ok = (failed_checks is not None) and (int(failed_checks) == 0)
            payload["report_pass"] = bool(score_ok and failed_ok and critical_checks_pass)
        except Exception:
            payload["report_pass"] = bool(critical_checks_pass)
    if bool(getattr(args, "commercial_readiness_enforce_pass", False)):
        if payload.get("report_pass") is False:
            payload["ok"] = False
            payload["returncode"] = int(payload.get("returncode", 2) or 2)
            payload["gate_failure"] = "commercial_readiness_enforce_pass_failed"
    return payload


def _publish_external_submission(args: argparse.Namespace, *, paths: Dict[str, str]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"requested": bool(getattr(args, "publish_external_submission", True))}
    if not bool(getattr(args, "publish_external_submission", True)):
        return payload
    if bool(getattr(args, "dry_run", False)):
        payload.update({"dry_run": True, "ok": True})
        return payload

    root = str(getattr(args, "external_submission_root", "runs/external_eval_submission")).rstrip("/")
    date_tag = str(getattr(args, "date_tag", "")).strip()
    out_dir = os.path.join(root, f"nightly_{date_tag}" if date_tag else "nightly_latest")
    os.makedirs(out_dir, exist_ok=True)

    copy_candidates = [
        paths.get("batch_summary_json", ""),
        paths.get("batch_summary_md", ""),
        paths.get("dashboard_html", ""),
        paths.get("dashboard_json", ""),
        paths.get("external_packet_json", ""),
        paths.get("commercial_readiness_json", ""),
        paths.get("commercial_readiness_csv", ""),
        paths.get("commercial_readiness_md", ""),
        paths.get("failure_latest_json", ""),
        paths.get("failure_latest_md", ""),
    ]
    copied: List[str] = []
    missing: List[str] = []
    for src in copy_candidates:
        p = str(src or "").strip()
        if not p:
            continue
        if not os.path.exists(p):
            missing.append(p)
            continue
        dst = os.path.join(out_dir, os.path.basename(p))
        shutil.copy2(p, dst)
        copied.append(dst)

    required = [
        str(paths.get("batch_summary_json", "")).strip(),
        str(paths.get("dashboard_html", "")).strip(),
        str(paths.get("external_packet_json", "")).strip(),
    ]
    strict = bool(getattr(args, "external_submission_strict", True))
    required_missing = [x for x in required if x and (not os.path.exists(x))]
    ok = bool((not strict) or (len(required_missing) == 0))

    payload.update(
        {
            "ok": ok,
            "out_dir": out_dir,
            "copied_files": copied,
            "missing_files": missing,
            "required_missing": required_missing,
            "strict": strict,
        }
    )
    return payload


def _build_paths(date_tag: str, prefix: str = "runs") -> Dict[str, str]:
    p = str(prefix).rstrip("/")
    return {
        "rebench_prefix": f"{p}/noncyclic_speed_accuracy_rebench_nightly_{date_tag}",
        "rebench_ai_runtime_profile_csv": f"{p}/ai_runtime_mode_profile_nightly_{date_tag}.csv",
        "rebench_ai_runtime_profile_json": f"{p}/ai_runtime_mode_profile_nightly_{date_tag}.json",
        "tuned_stability_prefix": f"{p}/long_stability_target_tuned_nightly_{date_tag}",
        "tuned_stability_csv": f"{p}/long_stability_target_tuned_nightly_{date_tag}.csv",
        "tuned_stability_json": f"{p}/long_stability_target_tuned_nightly_{date_tag}.json",
        "fetch_manifest": f"{p}/structure_sources_public_manifest_nightly_{date_tag}.csv",
        "fetch_summary": f"{p}/structure_sources_public_summary_nightly_{date_tag}.json",
        "quality_csv": f"{p}/structure_quality_curated_public_nightly_{date_tag}.csv",
        "quality_json": f"{p}/structure_quality_curated_public_nightly_{date_tag}.json",
        "ood_prefix": f"{p}/ood_first_validation_batch_nightly_{date_tag}",
        "ood_summary_json": f"{p}/ood_first_validation_batch_nightly_{date_tag}_summary.json",
        "ood_pair_csv": f"{p}/ood_first_validation_batch_nightly_{date_tag}_pair_metrics.csv",
        "ood_robust_prefix": f"{p}/ood_first_validation_batch_nightly_{date_tag}_robust_probe",
        "ood_robust_summary_json": f"{p}/ood_first_validation_batch_nightly_{date_tag}_robust_probe_summary.json",
        "ood_robust_pair_csv": f"{p}/ood_first_validation_batch_nightly_{date_tag}_robust_probe_pair_metrics.csv",
        "ood_dual_report_json": f"{p}/ood_dual_report_nightly_{date_tag}.json",
        "ood_dual_report_md": f"{p}/ood_dual_report_nightly_{date_tag}.md",
        "feature_csv": f"{p}/feature_matrix_per_target_nightly_{date_tag}.csv",
        "feature_json": f"{p}/feature_matrix_summary_nightly_{date_tag}.json",
        "internal_pdb_dir": f"data/internal_structures/nightly/{date_tag}",
        "dashboard_html": f"{p}/experiment_dashboard_nightly_{date_tag}.html",
        "dashboard_json": f"{p}/experiment_dashboard_nightly_{date_tag}.json",
        "claim_kinetics_csv": f"{p}/kinetics_equivalence_input_real_openmm_nightly_{date_tag}.csv",
        "claim_thermo_csv": f"{p}/thermo_equivalence_input_real_openmm_nightly_{date_tag}.csv",
        "claim_experiment_csv": f"{p}/experiment_consistency_input_real_openmm_nightly_{date_tag}.csv",
        "claim_diagnostics_csv": f"{p}/claim_input_diagnostics_nightly_{date_tag}.csv",
        "claim_diagnostics_json": f"{p}/claim_input_diagnostics_nightly_{date_tag}.json",
        "claim_input_summary_json": f"{p}/claim_input_real_openmm_summary_nightly_{date_tag}.json",
        "claim_prefix": f"{p}/allatom_claim_readiness_nightly_{date_tag}",
        "claim_correction_prefix": f"{p}/claim_metric_correction_loop_nightly_{date_tag}",
        "active_learning_prefix": f"{p}/active_learning_cycle_nightly_{date_tag}",
        "active_learning_summary_json": f"{p}/active_learning_cycle_nightly_{date_tag}_summary.json",
        "active_learning_summary_md": f"{p}/active_learning_cycle_nightly_{date_tag}_summary.md",
        "active_learning_live_unseen_hardcase_manifest_csv": f"{p}/active_learning_live_unseen_hardcase_manifest_nightly_{date_tag}.csv",
        "active_learning_live_unseen_hardcase_summary_json": f"{p}/active_learning_live_unseen_hardcase_manifest_nightly_{date_tag}.json",
        "special_case_prefix": f"{p}/special_case_pipeline_nightly_{date_tag}",
        "special_case_summary_json": f"{p}/special_case_pipeline_nightly_{date_tag}_summary.json",
        "special_case_summary_md": f"{p}/special_case_pipeline_nightly_{date_tag}_summary.md",
        "ood_measured20_prefix": f"{p}/ood_measured20_validation_batch_nightly_{date_tag}",
        "ood_measured20_summary_json": f"{p}/ood_measured20_validation_batch_nightly_{date_tag}_summary.json",
        "ood_measured20_pair_csv": f"{p}/ood_measured20_validation_batch_nightly_{date_tag}_pair_metrics.csv",
        "ood_measured40_prefix": f"{p}/ood_measured40_validation_batch_nightly_{date_tag}",
        "ood_measured40_summary_json": f"{p}/ood_measured40_validation_batch_nightly_{date_tag}_summary.json",
        "ood_measured40_pair_csv": f"{p}/ood_measured40_validation_batch_nightly_{date_tag}_pair_metrics.csv",
        "active_learning_priority_csv": f"{p}/active_learning_priority_targets_nightly_{date_tag}.csv",
        "active_learning_priority_json": f"{p}/active_learning_priority_targets_nightly_{date_tag}.json",
        "active_learning_priority_baseline_csv": f"{p}/active_learning_priority_targets_baseline_nightly_{date_tag}.csv",
        "active_learning_priority_baseline_json": f"{p}/active_learning_priority_targets_baseline_nightly_{date_tag}.json",
        "active_learning_priority_ab_csv": f"{p}/active_learning_priority_ab_nightly_{date_tag}.csv",
        "active_learning_priority_ab_json": f"{p}/active_learning_priority_ab_nightly_{date_tag}.json",
        "failure_latest_json": f"{p}/nightly_failure_latest.json",
        "failure_latest_md": f"{p}/nightly_failure_latest.md",
        "external_packet_json": f"{p}/external_eval_packet_v3_nightly_{date_tag}.json",
        "repro_snapshot_json": f"{p}/nightly_repro_snapshot_{date_tag}.json",
        "commercial_readiness_json": f"{p}/commercial_readiness_nightly_{date_tag}.json",
        "commercial_readiness_csv": f"{p}/commercial_readiness_nightly_{date_tag}.csv",
        "commercial_readiness_md": f"{p}/commercial_readiness_nightly_{date_tag}.md",
        "maintenance_summary_json": f"{p}/nightly_runs_maintenance_{date_tag}.json",
        "batch_summary_json": f"{p}/nightly_screening_batch_{date_tag}.json",
        "batch_summary_md": f"{p}/nightly_screening_batch_{date_tag}.md",
    }


def run_batch(args: argparse.Namespace) -> Dict[str, Any]:
    date_tag = str(args.date_tag or dt.date.today().isoformat())
    mode = str(args.mode).strip().lower()
    if mode not in ("smoke", "full"):
        raise ValueError("mode must be smoke|full")

    claim_profile_status = _apply_claim_profile_json(args)
    feature_profile_status = _apply_feature_profile_json(args)

    speed_profile_defaults = load_speed_profile_section(
        str(getattr(args, "speed_profile_defaults_json", "")).strip(),
        str(getattr(args, "speed_profile_defaults_section", "nightly")).strip() or "nightly",
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

    paths = _build_paths(date_tag=date_tag, prefix=str(args.runs_dir))
    os.makedirs(str(args.runs_dir), exist_ok=True)

    # Smoke mode keeps runtime short while validating the nightly chain.
    if mode == "smoke":
        rebench_stability_steps = 120
        rebench_checkpoints = "0,60,120"
        rebench_speed_steps = 40
        rebench_accuracy_steps = 20
        rebench_accuracy_runs = 1
        feature_steps = 60
        feature_samples = 1
    else:
        rebench_stability_steps = 1200
        rebench_checkpoints = "0,100,300,600,900,1200"
        rebench_speed_steps = 160
        rebench_accuracy_steps = 60
        rebench_accuracy_runs = 3
        feature_steps = 240
        feature_samples = 3

    env = os.environ.copy()
    env["FORCE_RUST_HIP"] = "1"
    env["RUST_HIP_USE_GPU_NBLIST_BUILDER"] = "1"

    rebench_runtime_mode_status = _choose_rebench_ai_runtime_mode(args=args, env=env, paths=paths)
    args.rebench_ai_runtime_mode = str(
        rebench_runtime_mode_status.get("selected_mode", getattr(args, "rebench_ai_runtime_mode", "scripted"))
    )

    long_stability_gate_policy = str(args.long_stability_gate_policy).strip().lower()
    if long_stability_gate_policy not in {"strict", "pragmatic"}:
        raise ValueError("long_stability_gate_policy must be strict|pragmatic")

    claim_accuracy_csv = str(getattr(args, "claim_accuracy_csv", "")).strip()
    if not claim_accuracy_csv:
        claim_accuracy_csv = f"{paths['rebench_prefix']}_accuracy.csv"

    measured20_sources_csv_path = _resolve_input_path(str(getattr(args, "ood_measured20_sources_csv", "")).strip())
    measured20_tags_csv_path = _resolve_input_path(str(getattr(args, "ood_measured20_tags_csv", "")).strip())
    measured40_sources_csv_path = _resolve_input_path(str(getattr(args, "ood_measured40_sources_csv", "")).strip())
    measured40_tags_csv_path = _resolve_input_path(str(getattr(args, "ood_measured40_tags_csv", "")).strip())
    external_manifest_path = _resolve_input_path(str(args.external_manifest))
    strict_summary_json_path = _resolve_input_path(str(args.strict_summary_json))
    claim_policy_json_path = _resolve_input_path(str(args.claim_policy_json))
    (
        external_packet_accuracy_external_csv_path,
        external_packet_accuracy_external_candidates,
    ) = _resolve_external_packet_accuracy_external_csv(
        args=args,
        paths=paths,
        strict_summary_json_path=strict_summary_json_path,
    )
    selected_external_candidate: Dict[str, Any] = {}
    if external_packet_accuracy_external_csv_path:
        selected_external_candidate = next(
            (
                c
                for c in external_packet_accuracy_external_candidates
                if str(c.get("path", "")) == str(external_packet_accuracy_external_csv_path)
            ),
            {},
        )
    commercial_traj_tail_csv_path = _resolve_input_path(
        str(getattr(args, "commercial_readiness_trajectory_target_tail_csv", "")).strip()
    )
    active_learning_stage2_csv = _resolve_input_path(f"{paths['rebench_prefix']}_stage2.csv")
    if not os.path.exists(active_learning_stage2_csv):
        fallback_stage2 = _resolve_input_path(str(getattr(args, "active_learning_stage2_csv", "")))
        if os.path.exists(fallback_stage2):
            active_learning_stage2_csv = fallback_stage2
    dashboard_compare_csv_path = _resolve_dashboard_compare_csv(
        str(args.runs_dir),
        explicit_compare_csv=str(getattr(args, "dashboard_compare_csv", "")).strip(),
        current_feature_csv=paths["feature_csv"],
    )
    dashboard_external_pdb_glob = str(getattr(args, "dashboard_pdb_glob", "")).strip()
    if not dashboard_external_pdb_glob:
        dashboard_external_pdb_glob = str(args.public_out_dir).rstrip("/") + f"/{date_tag}/*.pdb"
    dashboard_include_internal_pdb = bool(getattr(args, "dashboard_include_internal_pdb", True))
    dashboard_internal_pdb_dir = str(getattr(args, "dashboard_internal_pdb_dir", "")).strip()
    if not dashboard_internal_pdb_dir:
        dashboard_internal_pdb_dir = str(paths.get("internal_pdb_dir", "")).strip()
    dashboard_internal_pdb_glob = str(getattr(args, "dashboard_internal_pdb_glob", "")).strip()
    if (not dashboard_internal_pdb_glob) and dashboard_include_internal_pdb and dashboard_internal_pdb_dir:
        dashboard_internal_pdb_glob = dashboard_internal_pdb_dir.rstrip("/") + "/*.pdb"
    # Backward-compatible alias used in summary and existing integrations.
    dashboard_pdb_glob = dashboard_external_pdb_glob
    dashboard_target_filters = _targets_to_dashboard_filters(str(args.targets))

    resolved_inputs = {
        "external_manifest": external_manifest_path,
        "strict_summary_json": strict_summary_json_path,
        "claim_policy_json": claim_policy_json_path,
        "active_learning_stage2_csv": active_learning_stage2_csv,
        "rebench_use_ai_router": bool(getattr(args, "rebench_use_ai_router", True)),
        "rebench_ai_runtime_mode": str(getattr(args, "rebench_ai_runtime_mode", "scripted")),
        "rebench_speed_profile_preserve_runtime_mode": bool(
            getattr(args, "rebench_speed_profile_preserve_runtime_mode", True)
        ),
        "rebench_ai_disable_exploration": bool(getattr(args, "rebench_ai_disable_exploration", True)),
        "rebench_ai_use_hip_graph": bool(getattr(args, "rebench_ai_use_hip_graph", False)),
        "rebench_ai_graph_warmup_iters": int(getattr(args, "rebench_ai_graph_warmup_iters", 2)),
        "rebench_ai_router_checkpoint": str(getattr(args, "rebench_ai_router_checkpoint", "")).strip(),
        "rebench_ai_router_checkpoint_strict": bool(
            getattr(args, "rebench_ai_router_checkpoint_strict", False)
        ),
        "rebench_ai_runtime_selected_mode": str(rebench_runtime_mode_status.get("selected_mode", "")),
        "rebench_ai_runtime_selection_source": str(rebench_runtime_mode_status.get("selection_source", "")),
        "rebench_ai_runtime_profile_json": str(paths.get("rebench_ai_runtime_profile_json", "")),
        "rebench_ai_runtime_profile_csv": str(paths.get("rebench_ai_runtime_profile_csv", "")),
        "ood_measured20_sources_csv": measured20_sources_csv_path,
        "ood_measured20_tags_csv": measured20_tags_csv_path,
        "ood_measured40_sources_csv": measured40_sources_csv_path,
        "ood_measured40_tags_csv": measured40_tags_csv_path,
        "dashboard_compare_csv": dashboard_compare_csv_path,
        "dashboard_pdb_glob": dashboard_pdb_glob,
        "dashboard_external_pdb_glob": dashboard_external_pdb_glob,
        "dashboard_internal_pdb_glob": dashboard_internal_pdb_glob,
        "dashboard_internal_pdb_dir": dashboard_internal_pdb_dir,
        "dashboard_include_internal_pdb": bool(dashboard_include_internal_pdb),
        "external_packet_accuracy_external_csv": external_packet_accuracy_external_csv_path,
        "external_packet_accuracy_external_candidate_count": int(len(external_packet_accuracy_external_candidates)),
        "external_packet_accuracy_external_selected": selected_external_candidate,
        "commercial_readiness_trajectory_target_tail_csv": commercial_traj_tail_csv_path,
    }
    preflight_status = _preflight_validate_inputs(
        args=args,
        strict_summary_json_path=strict_summary_json_path,
        external_manifest_path=external_manifest_path,
        external_packet_accuracy_external_csv_path=external_packet_accuracy_external_csv_path,
        claim_policy_json_path=claim_policy_json_path,
    )
    if (not bool(getattr(args, "dry_run", False))) and (not bool(preflight_status.get("pass", False))):
        summary = {
            "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
            "date_tag": date_tag,
            "mode": mode,
            "long_stability_gate_policy": long_stability_gate_policy,
            "skip_speed_rebench": bool(getattr(args, "skip_speed_rebench", False)),
            "targets": str(args.targets),
            "dry_run": bool(args.dry_run),
            "pass": False,
            "failed_step_index": 0,
            "total_steps": 0,
            "executed_steps": 0,
            "long_stability_status": {},
            "ood_status": {},
            "ood_measured20_status": {},
            "ood_measured40_status": {},
            "active_learning_status": {},
            "active_learning_live_unseen_hardcase_status": {},
            "active_learning_priority_status": {},
            "active_learning_priority_ab_status": {},
            "dashboard_status": {},
            "commercial_readiness_status": {},
            "special_case_status": {},
            "claim_status": {},
            "claim_profile": claim_profile_status,
            "feature_profile": feature_profile_status,
            "rebench_ai_runtime_mode_status": rebench_runtime_mode_status,
            "attempts_csv_links": _resolve_attempts_csv_links(str(args.runs_dir), date_tag),
            "speed_profile_defaults": {
                "json": str(getattr(args, "speed_profile_defaults_json", "")).strip(),
                "section": str(getattr(args, "speed_profile_defaults_section", "nightly")).strip()
                or "nightly",
                "resolved": resolved_speed_profile,
            },
            "claim_require_initial_ready": bool(getattr(args, "claim_require_initial_ready", True)),
            "initial_claim_requirement_failed": False,
            "measured_proxy_requirement_failed": False,
            "measured_proxy_failures": [],
            "dashboard_metrics_requirement_failed": False,
            "preflight_status": preflight_status,
            "resolved_inputs": resolved_inputs,
            "paths": paths,
            "claim_accuracy_csv": claim_accuracy_csv,
            "results": [],
            "ood_dual_report_status": {
                "requested": bool(getattr(args, "run_ood_dual_report", True)),
                "dry_run": bool(getattr(args, "dry_run", False)),
                "ok": False,
                "returncode": 2,
                "reason": "preflight_input_validation_failed",
            },
            "external_packet_status": {
                "requested": bool(getattr(args, "run_external_packet", True)),
                "dry_run": bool(getattr(args, "dry_run", False)),
                "ok": False,
                "returncode": 2,
                "reason": "preflight_input_validation_failed",
            },
            "commercial_readiness_report_status": {
                "requested": bool(getattr(args, "run_commercial_readiness_report", True)),
                "dry_run": bool(getattr(args, "dry_run", False)),
                "ok": False,
                "returncode": 2,
                "reason": "preflight_input_validation_failed",
            },
            "external_submission_status": {
                "requested": bool(getattr(args, "publish_external_submission", True)),
                "dry_run": bool(getattr(args, "dry_run", False)),
                "ok": False,
                "reason": "preflight_input_validation_failed",
            },
            "maintenance": {
                "requested": bool(getattr(args, "run_runs_maintenance", True)),
                "ok": False,
                "reason": "preflight_input_validation_failed",
            },
            "post_process_failures": [
                {
                    "name": "preflight_validation",
                    "returncode": 2,
                    "reason": "preflight_input_validation_failed",
                    "failures": preflight_status.get("failures", []),
                }
            ],
        }
        with open(paths["batch_summary_json"], "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        md_lines = [
            "# Nightly Screening Batch",
            "",
            f"- date_tag: {date_tag}",
            f"- mode: {mode}",
            f"- pass: False",
            f"- failed_step_index: 0",
            f"- preflight_pass: {bool(preflight_status.get('pass', False))}",
            f"- preflight_failures: {preflight_status.get('failures', [])}",
            f"- summary_json: {paths['batch_summary_json']}",
        ]
        with open(paths["batch_summary_md"], "w", encoding="utf-8") as f:
            f.write("\n".join(md_lines) + "\n")
        summary["failure_latest_report"] = _write_failure_latest_report(summary, paths)
        summary["reproducibility_snapshot"] = _write_reproducibility_snapshot(
            args=args,
            paths=paths,
            summary=summary,
            resolved_inputs=resolved_inputs,
            env=env,
        )
        with open(paths["batch_summary_json"], "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        return summary

    commands: List[Dict[str, Any]] = []
    rebench_cmd: List[str] = [
        sys.executable,
        "tools/run_openmm_2bead_rebench.py",
        "--targets",
        str(args.targets),
        "--date-tag",
        date_tag,
        "--skip-openmm-generate",
        "--external-manifest",
        str(external_manifest_path),
        "--stability-runs",
        "1",
        "--stability-steps",
        str(rebench_stability_steps),
        "--stability-checkpoints",
        rebench_checkpoints,
        "--speed-steps",
        str(rebench_speed_steps),
        "--speed-runs",
        "1",
        "--speed-warmup-steps",
        "30",
        "--speed-mode",
        str(args.speed_mode),
        "--speed-mode-replicas",
        str(args.speed_mode_replicas),
        "--speed-profile-max-replicas",
        str(args.speed_profile_max_replicas),
        "--ai-runtime-mode",
        str(getattr(args, "rebench_ai_runtime_mode", "scripted")),
        "--speed-profile-preserve-runtime-mode"
        if bool(getattr(args, "rebench_speed_profile_preserve_runtime_mode", True))
        else "--no-speed-profile-preserve-runtime-mode",
        "--ai-graph-warmup-iters",
        str(int(getattr(args, "rebench_ai_graph_warmup_iters", 2))),
        "--ai-interval",
        str(int(getattr(args, "ai_interval", 1))),
        "--target-ai-interval-policy",
        str(getattr(args, "target_ai_interval_policy", "")),
        "--accuracy-steps",
        str(rebench_accuracy_steps),
        "--accuracy-runs",
        str(rebench_accuracy_runs),
        "--with-fallback",
        "--force-rust",
        "--out-prefix",
        paths["rebench_prefix"],
    ]
    if bool(getattr(args, "rebench_use_ai_router", True)):
        rebench_cmd.append("--use-ai-router")
    else:
        rebench_cmd.append("--no-use-ai-router")
    if bool(getattr(args, "rebench_ai_disable_exploration", True)):
        rebench_cmd.append("--ai-disable-exploration")
    else:
        rebench_cmd.append("--no-ai-disable-exploration")
    if bool(getattr(args, "rebench_ai_use_hip_graph", False)):
        rebench_cmd.append("--ai-use-hip-graph")
    else:
        rebench_cmd.append("--no-ai-use-hip-graph")
    rebench_ai_ckpt = str(getattr(args, "rebench_ai_router_checkpoint", "")).strip()
    if rebench_ai_ckpt:
        rebench_cmd.extend(["--ai-router-checkpoint", rebench_ai_ckpt])
    if bool(getattr(args, "rebench_ai_router_checkpoint_strict", False)):
        rebench_cmd.append("--ai-router-checkpoint-strict")
    else:
        rebench_cmd.append("--no-ai-router-checkpoint-strict")
    if bool(getattr(args, "skip_speed_rebench", False)):
        rebench_cmd.append("--skip-speed-rebench")
    if str(args.rebench_stability_profile_json).strip():
        rebench_cmd.extend(["--stability-profile-json", str(args.rebench_stability_profile_json)])
    if long_stability_gate_policy == "strict":
        rebench_cmd.append("--enforce-long-stability-gate")

    commands.append(
        {
            "name": "rebench",
            "cmd": rebench_cmd,
        }
    )

    if bool(args.run_tuned_long_stability):
        commands.append(
            {
                "name": "tuned_long_stability_fallback",
                "cmd": [
                    sys.executable,
                    "tools/run_target_tuned_long_stability.py",
                    "--profile-json",
                    str(args.tuned_long_stability_profile_json),
                    "--runs",
                    "1",
                    "--steps",
                    str(rebench_stability_steps),
                    "--checkpoints",
                    rebench_checkpoints,
                    "--noise",
                    "0.08",
                    "--seed",
                    "1234",
                    "--cutoff",
                    "12.0",
                    "--skin",
                    "2.0",
                    "--max-neighbors",
                    "100",
                    "--max-atoms-per-cell",
                    "64",
                    "--rebuild-stride",
                    "4",
                    "--force-rust",
                    "--force-backend",
                    "auto",
                    "--clash-cutoff",
                    "2.0",
                    "--aligned-rmsd-threshold",
                    "2.0",
                    "--energy-drift-threshold",
                    "0.30",
                    "--rg-delta-threshold",
                    "1.0",
                    "--max-clash-pairs",
                    "2",
                    "--date-tag",
                    date_tag,
                    "--out-prefix",
                    paths["tuned_stability_prefix"],
                    "--out-csv",
                    paths["tuned_stability_csv"],
                    "--out-json",
                    paths["tuned_stability_json"],
                ],
            }
        )

    commands.append(
        {
            "name": "fetch_public_structures",
            "cmd": [
                sys.executable,
                "tools/fetch_public_structure_set.py",
                "--sources-csv",
                str(args.sources_csv),
                "--targets",
                str(args.targets),
                "--download-pdb",
                "--download-afdb",
                "--afdb-model-versions",
                str(args.afdb_model_versions),
                "--out-dir",
                str(args.public_out_dir).rstrip("/") + f"/{date_tag}",
                "--out-manifest-csv",
                paths["fetch_manifest"],
                "--out-summary-json",
                paths["fetch_summary"],
            ],
        }
    )

    commands.append(
        {
            "name": "curate_structure_quality",
            "cmd": [
                sys.executable,
                "tools/curate_structure_quality.py",
                "--manifest-csv",
                paths["fetch_manifest"],
                "--out-csv",
                paths["quality_csv"],
                "--out-json",
                paths["quality_json"],
            ],
        }
    )

    if bool(getattr(args, "run_ood_gate", True)):
        ood_cmd: List[str] = [
            sys.executable,
            "tools/run_ood_first_validation_batch.py",
            "--targets",
            str(args.targets),
            "--date-tag",
            date_tag,
            "--sources-csv",
            str(args.sources_csv),
            "--out-dir",
            str(args.public_out_dir).rstrip("/") + f"/{date_tag}",
            "--out-prefix",
            paths["ood_prefix"],
            "--manifest-csv",
            paths["fetch_manifest"],
            "--skip-fetch",
            "--min-pairs",
            str(int(args.ood_min_pairs)),
            "--max-mean-pair-rmsd",
            str(float(args.ood_max_mean_pair_rmsd)),
            "--max-length-ratio",
            str(float(args.ood_max_length_ratio)),
            "--max-windowed-rmsd",
            str(float(args.ood_max_windowed_rmsd)),
            "--max-proxy-rows",
            str(int(getattr(args, "ood_max_proxy_rows", 0))),
        ]
        if bool(getattr(args, "ood_require_real_afdb", True)):
            ood_cmd.append("--require-real-afdb")
        if bool(getattr(args, "ood_enable_proxy_manifest", True)):
            ood_cmd.append("--enable-proxy-manifest")
        else:
            ood_cmd.append("--no-enable-proxy-manifest")
        if bool(getattr(args, "ood_enable_windowed_match", True)):
            ood_cmd.append("--enable-windowed-match")
        else:
            ood_cmd.append("--no-enable-windowed-match")
        if bool(getattr(args, "ood_strict_fail", True)):
            ood_cmd.append("--strict-fail")
        commands.append({"name": "ood_first_gate", "cmd": ood_cmd})

    if bool(getattr(args, "run_ood_measured20", False)):
        measured20_cmd: List[str] = [
            sys.executable,
            "tools/run_ood_first_validation_batch.py",
            "--targets",
            str(getattr(args, "ood_measured20_targets", "sources_all")),
            "--date-tag",
            date_tag,
            "--sources-csv",
            str(measured20_sources_csv_path),
            "--out-dir",
            str(args.public_out_dir).rstrip("/") + f"/{date_tag}_ood_measured20",
            "--out-prefix",
            paths["ood_measured20_prefix"],
            "--min-pairs",
            str(int(args.ood_measured20_min_pairs)),
            "--max-mean-pair-rmsd",
            str(float(args.ood_measured20_max_mean_rmsd)),
            "--max-length-ratio",
            str(float(args.ood_max_length_ratio)),
            "--max-windowed-rmsd",
            str(float(args.ood_max_windowed_rmsd)),
            "--max-proxy-rows",
            str(int(getattr(args, "ood_measured20_max_proxy_rows", 0))),
        ]
        if bool(getattr(args, "ood_measured20_require_real_afdb", True)):
            measured20_cmd.append("--require-real-afdb")
        if bool(getattr(args, "ood_measured20_enable_proxy_manifest", False)):
            measured20_cmd.append("--enable-proxy-manifest")
        else:
            measured20_cmd.append("--no-enable-proxy-manifest")
        if bool(getattr(args, "ood_measured20_strict_fail", True)):
            measured20_cmd.append("--strict-fail")
        if str(measured20_tags_csv_path).strip():
            measured20_cmd.extend(["--domain-tags-csv", str(measured20_tags_csv_path)])
        if int(getattr(args, "ood_measured20_min_domain_coverage", 0) or 0) > 0:
            measured20_cmd.extend(["--min-domain-coverage", str(int(args.ood_measured20_min_domain_coverage))])
        if bool(getattr(args, "ood_enable_windowed_match", True)):
            measured20_cmd.append("--enable-windowed-match")
        else:
            measured20_cmd.append("--no-enable-windowed-match")
        commands.append({"name": "ood_measured20_gate", "cmd": measured20_cmd})

    if bool(getattr(args, "run_ood_measured40", False)):
        measured40_cmd: List[str] = [
            sys.executable,
            "tools/run_ood_first_validation_batch.py",
            "--targets",
            str(getattr(args, "ood_measured40_targets", "sources_all")),
            "--date-tag",
            date_tag,
            "--sources-csv",
            str(measured40_sources_csv_path),
            "--out-dir",
            str(args.public_out_dir).rstrip("/") + f"/{date_tag}_ood_measured40",
            "--out-prefix",
            paths["ood_measured40_prefix"],
            "--min-pairs",
            str(int(args.ood_measured40_min_pairs)),
            "--max-mean-pair-rmsd",
            str(float(args.ood_measured40_max_mean_rmsd)),
            "--max-length-ratio",
            str(float(args.ood_max_length_ratio)),
            "--max-windowed-rmsd",
            str(float(args.ood_max_windowed_rmsd)),
            "--max-proxy-rows",
            str(int(getattr(args, "ood_measured40_max_proxy_rows", 0))),
        ]
        if bool(getattr(args, "ood_measured40_require_real_afdb", True)):
            measured40_cmd.append("--require-real-afdb")
        if bool(getattr(args, "ood_measured40_enable_proxy_manifest", False)):
            measured40_cmd.append("--enable-proxy-manifest")
        else:
            measured40_cmd.append("--no-enable-proxy-manifest")
        if bool(getattr(args, "ood_measured40_strict_fail", True)):
            measured40_cmd.append("--strict-fail")
        if str(measured40_tags_csv_path).strip():
            measured40_cmd.extend(["--domain-tags-csv", str(measured40_tags_csv_path)])
        if int(getattr(args, "ood_measured40_min_domain_coverage", 0) or 0) > 0:
            measured40_cmd.extend(["--min-domain-coverage", str(int(args.ood_measured40_min_domain_coverage))])
        if bool(getattr(args, "ood_enable_windowed_match", True)):
            measured40_cmd.append("--enable-windowed-match")
        else:
            measured40_cmd.append("--no-enable-windowed-match")
        commands.append({"name": "ood_measured40_gate", "cmd": measured40_cmd})

    feature_cmd: List[str] = [
        sys.executable,
        "tools/collect_feature_matrix.py",
        "--targets",
        str(args.targets),
        "--samples",
        str(feature_samples),
        "--steps",
        str(feature_steps),
        "--save-stride",
        "20",
        "--noise",
        "0.08",
        "--force-rust",
        "--ai-correction-active",
        "--out-csv",
        paths["feature_csv"],
        "--out-json",
        paths["feature_json"],
    ]
    feature_cmd.append(
        "--enable-control-perturbation"
        if bool(getattr(args, "feature_enable_control_perturbation", True))
        else "--no-enable-control-perturbation"
    )
    feature_cmd.extend(
        [
            "--control-perturbation-seed",
            str(int(getattr(args, "feature_control_perturbation_seed", 20260222))),
            "--perturb-ionic-strength-grid",
            str(getattr(args, "feature_perturb_ionic_strength_grid", "0.05,0.15,0.30,0.50")),
            "--perturb-ptm-count-grid",
            str(getattr(args, "feature_perturb_ptm_count_grid", "0,1,2,3")),
            "--perturb-temperature-end-grid",
            str(getattr(args, "feature_perturb_temperature_end_grid", "300,350,400,500")),
            "--perturb-hydro-scale-grid",
            str(getattr(args, "feature_perturb_hydro_scale_grid", "0.8,1.0,1.2")),
            "--perturb-force-scale-mult-grid",
            str(getattr(args, "feature_perturb_force_scale_mult_grid", "0.9,1.0,1.1")),
            "--control-prefix",
            str(getattr(args, "feature_control_prefix", "control_")),
            "--observed-prefix",
            str(getattr(args, "feature_observed_prefix", "observed_")),
        ]
    )
    if bool(dashboard_include_internal_pdb):
        feature_cmd.extend(
            [
                "--export-internal-pdb",
                "--internal-pdb-out-dir",
                str(dashboard_internal_pdb_dir),
                "--internal-pdb-max-per-target",
                str(int(getattr(args, "dashboard_internal_pdb_per_target", 1))),
            ]
        )
    commands.append({"name": "collect_feature_matrix", "cmd": feature_cmd})

    commands.append(
        {
            "name": "build_claim_inputs",
            "cmd": [
                sys.executable,
                "tools/build_claim_inputs_from_openmm_manifest.py",
                "--manifest-csv",
                str(external_manifest_path),
                "--targets",
                str(args.targets),
                "--out-kinetics-csv",
                paths["claim_kinetics_csv"],
                "--out-thermo-csv",
                paths["claim_thermo_csv"],
                "--out-experiment-csv",
                paths["claim_experiment_csv"],
                "--out-diagnostics-csv",
                paths["claim_diagnostics_csv"],
                "--out-diagnostics-json",
                paths["claim_diagnostics_json"],
                "--out-json",
                paths["claim_input_summary_json"],
                "--split-mode",
                str(args.claim_split_mode),
                "--split-replicas",
                str(int(args.claim_split_replicas)),
                "--split-window-frames",
                str(int(args.claim_split_window_frames)),
                "--split-window-stride",
                str(int(args.claim_split_window_stride)),
                "--min-effective-frames",
                str(int(args.claim_min_effective_frames)),
                "--thermo-agg-method",
                str(args.claim_thermo_agg_method),
                "--kinetics-agg-method",
                str(args.claim_kinetics_agg_method),
                "--experiment-agg-method",
                str(args.claim_experiment_agg_method),
                "--trim-fraction",
                str(float(args.claim_trim_fraction)),
                "--tail-clip-low",
                str(float(args.claim_tail_clip_low)),
                "--tail-clip-high",
                str(float(args.claim_tail_clip_high)),
                "--pmf-pseudocount",
                str(float(args.claim_pmf_pseudocount)),
                "--kinetics-min-signal-std",
                str(float(args.claim_kinetics_min_signal_std)),
                "--kinetics-min-denom-eps",
                str(float(args.claim_kinetics_min_denom_eps)),
            ],
        }
    )

    commands.append(
        {
            "name": "run_claim_readiness",
            "cmd": [
                sys.executable,
                "tools/run_allatom_claim_readiness.py",
                "--strict-summary-json",
                str(strict_summary_json_path),
                "--accuracy-external-csv",
                claim_accuracy_csv,
                "--kinetics-input-csv",
                paths["claim_kinetics_csv"],
                "--thermo-input-csv",
                paths["claim_thermo_csv"],
                "--experiment-input-csv",
                paths["claim_experiment_csv"],
                "--intermediate-prefix",
                paths["claim_prefix"],
                "--gate-out-json",
                f"{paths['claim_prefix']}_gate.json",
                "--gate-out-csv",
                f"{paths['claim_prefix']}_gate.csv",
                "--out-json",
                f"{paths['claim_prefix']}_summary.json",
                "--out-csv",
                f"{paths['claim_prefix']}_summary.csv",
                "--out-md",
                f"{paths['claim_prefix']}_summary.md",
            ],
        }
    )

    if bool(args.run_claim_correction):
        correction_cmd = [
            sys.executable,
            "tools/run_claim_metric_correction_loop.py",
            "--policy-json",
            str(claim_policy_json_path),
            "--strict-summary-json",
            str(strict_summary_json_path),
            "--accuracy-external-csv",
            claim_accuracy_csv,
            "--thermo-input-csv",
            paths["claim_thermo_csv"],
            "--kinetics-input-csv",
            paths["claim_kinetics_csv"],
            "--experiment-input-csv",
            paths["claim_experiment_csv"],
            "--max-iters",
            str(int(args.claim_correction_max_iters)),
            "--target-margin",
            str(float(args.claim_correction_target_margin)),
            "--damping",
            str(float(args.claim_correction_damping)),
            "--out-prefix",
            paths["claim_correction_prefix"],
        ]
        if bool(args.claim_correction_enforce_ready):
            correction_cmd.append("--enforce-complete-claim")
        commands.append({"name": "run_claim_correction", "cmd": correction_cmd})

    if bool(getattr(args, "run_active_learning", False)):
        priority_enabled = bool(getattr(args, "active_learning_priority_enabled", True))
        effective_hardcase_manifest_csv = str(
            getattr(args, "active_learning_curriculum_hardcase_manifest_csv", "")
        ).strip()
        if (
            (not effective_hardcase_manifest_csv)
            and bool(getattr(args, "active_learning_auto_hardcase_from_live_unseen", True))
        ):
            hardcase_cmd: List[str] = [
                sys.executable,
                "tools/build_live_unseen_hardcase_manifest.py",
                "--live-manifest-csv",
                str(args.active_learning_live_unseen_manifest_csv),
                "--failure-breakdown-csv",
                str(args.active_learning_live_unseen_failure_breakdown_csv),
                "--min-fail-count",
                str(float(args.active_learning_live_unseen_hardcase_min_fail_count)),
                "--max-targets",
                str(int(args.active_learning_live_unseen_hardcase_max_targets)),
                "--out-manifest-csv",
                paths["active_learning_live_unseen_hardcase_manifest_csv"],
                "--out-summary-json",
                paths["active_learning_live_unseen_hardcase_summary_json"],
            ]
            commands.append(
                {
                    "name": "build_live_unseen_hardcase_manifest",
                    "cmd": hardcase_cmd,
                }
            )
            effective_hardcase_manifest_csv = paths["active_learning_live_unseen_hardcase_manifest_csv"]
        active_learning_ood_pair_csv = paths["ood_pair_csv"]
        if str(args.targets).strip().lower() != "all":
            if bool(getattr(args, "run_ood_measured40", False)):
                active_learning_ood_pair_csv = paths["ood_measured40_pair_csv"]
            elif bool(getattr(args, "run_ood_measured20", False)):
                active_learning_ood_pair_csv = paths["ood_measured20_pair_csv"]
        if bool(getattr(args, "active_learning_priority_enabled", True)):
            priority_ood_pair_csv = _resolve_input_path(str(getattr(args, "active_learning_priority_ood_pair_csv", "")).strip())
            if not priority_ood_pair_csv:
                priority_ood_pair_csv = active_learning_ood_pair_csv
            priority_feature_csv = _resolve_input_path(
                str(getattr(args, "active_learning_priority_feature_csv", "")).strip()
            ) or _resolve_input_path(str(paths.get("feature_csv", "")).strip())
            base_priority_cmd: List[str] = [
                sys.executable,
                "tools/build_active_learning_priority_targets.py",
                "--targets",
                str(args.targets),
                "--ood-pair-csv",
                str(priority_ood_pair_csv),
                "--ood-min-rmsd",
                str(float(args.active_learning_priority_ood_min_rmsd)),
                "--ood-topk",
                str(int(args.active_learning_priority_ood_topk)),
                "--oversize-breakdown-csv",
                str(args.active_learning_priority_oversize_csv),
                "--oversize-topk",
                str(int(args.active_learning_priority_oversize_topk)),
                "--oversize-target-col",
                str(args.active_learning_priority_oversize_target_col),
                "--feature-csv",
                str(priority_feature_csv),
                "--feature-target-col",
                str(args.active_learning_priority_feature_target_col),
                "--feature-rmsd-col",
                str(args.active_learning_priority_feature_rmsd_col),
                "--feature-violations-col",
                str(args.active_learning_priority_feature_violations_col),
                "--feature-control-prefix",
                str(args.active_learning_priority_feature_control_prefix),
                "--feature-min-control-levels",
                str(float(args.active_learning_priority_feature_min_control_levels)),
            ]
            commands.append(
                {
                    "name": "build_active_learning_priority_targets_baseline",
                    "cmd": [
                        *base_priority_cmd,
                        "--feature-topk",
                        "0",
                        "--out-csv",
                        paths["active_learning_priority_baseline_csv"],
                        "--out-json",
                        paths["active_learning_priority_baseline_json"],
                    ],
                }
            )
            commands.append(
                {
                    "name": "build_active_learning_priority_targets",
                    "cmd": [
                        *base_priority_cmd,
                        "--feature-topk",
                        str(int(args.active_learning_priority_feature_topk)),
                        "--out-csv",
                        paths["active_learning_priority_csv"],
                        "--out-json",
                        paths["active_learning_priority_json"],
                    ],
                }
            )
            commands.append(
                {
                    "name": "evaluate_active_learning_priority_ab",
                    "cmd": [
                        sys.executable,
                        "tools/evaluate_active_learning_priority_ab.py",
                        "--baseline-csv",
                        paths["active_learning_priority_baseline_csv"],
                        "--candidate-csv",
                        paths["active_learning_priority_csv"],
                        "--ood-pair-csv",
                        str(priority_ood_pair_csv),
                        "--ood-min-rmsd",
                        str(float(args.active_learning_priority_ood_min_rmsd)),
                        "--out-json",
                        paths["active_learning_priority_ab_json"],
                        "--out-csv",
                        paths["active_learning_priority_ab_csv"],
                    ],
                }
            )

        priority_csv_for_active = paths["active_learning_priority_csv"] if priority_enabled else ""
        priority_bonus_for_active = float(args.active_learning_priority_bonus) if priority_enabled else 0.0
        active_cmd: List[str] = [
            sys.executable,
            "tools/run_active_learning_cycle.py",
            "--date-tag",
            date_tag,
            "--targets",
            str(args.targets),
            "--out-prefix",
            paths["active_learning_prefix"],
            "--ood-pair-csv",
            active_learning_ood_pair_csv,
            "--accuracy-external-csv",
            claim_accuracy_csv,
            "--stage2-csv",
            active_learning_stage2_csv,
            "--hard-mining-topk",
            str(int(args.active_learning_topk)),
            "--hard-mining-priority-targets-csv",
            priority_csv_for_active,
            "--hard-mining-priority-target-col",
            "target",
            "--hard-mining-priority-bonus",
            str(float(priority_bonus_for_active)),
            "--curriculum-base-manifest-csv",
            str(args.active_learning_curriculum_base_manifest_csv),
            "--curriculum-checkpoint-dir",
            str(args.active_learning_curriculum_checkpoint_dir),
            "--curriculum-max-targets",
            str(int(args.active_learning_curriculum_max_targets)),
            "--curriculum-out-merged-manifest-csv",
            f"{paths['active_learning_prefix']}_manifest.csv",
            "--curriculum-out-merged-summary-json",
            f"{paths['active_learning_prefix']}_manifest_summary.json",
            "--curriculum-summary-json",
            f"{paths['active_learning_prefix']}_curriculum_summary.json",
            "--curriculum-summary-csv",
            f"{paths['active_learning_prefix']}_curriculum_summary.csv",
            "--curriculum-out-json",
            f"{paths['active_learning_prefix']}_curriculum_out.json",
            "--claim-policy-json",
            str(claim_policy_json_path),
            "--claim-strict-summary-json",
            str(strict_summary_json_path),
            "--claim-accuracy-external-csv",
            claim_accuracy_csv,
            "--claim-thermo-input-csv",
            paths["claim_thermo_csv"],
            "--claim-kinetics-input-csv",
            paths["claim_kinetics_csv"],
            "--claim-experiment-input-csv",
            paths["claim_experiment_csv"],
            "--claim-max-iters",
            str(int(args.active_learning_claim_max_iters)),
            "--claim-target-margin",
            str(float(args.active_learning_claim_target_margin)),
            "--claim-damping",
            str(float(args.active_learning_claim_damping)),
            "--claim-out-prefix",
            f"{paths['active_learning_prefix']}_claim",
        ]
        if bool(str(effective_hardcase_manifest_csv).strip()):
            active_cmd.extend(
                [
                    "--curriculum-hardcase-manifest-csv",
                    str(effective_hardcase_manifest_csv),
                ]
            )
        if bool(args.active_learning_skip_curriculum_training):
            active_cmd.append("--skip-curriculum-training")
        if bool(args.active_learning_skip_claim_correction):
            active_cmd.append("--skip-claim-correction")
        else:
            active_cmd.append("--no-skip-claim-correction")
        if bool(args.active_learning_dry_run):
            active_cmd.append("--dry-run")
        if bool(args.active_learning_curriculum_skip_manifest_build):
            active_cmd.append("--curriculum-skip-manifest-build")
        if bool(args.active_learning_claim_enforce_complete):
            active_cmd.append("--claim-enforce-complete")
        commands.append({"name": "run_active_learning_cycle", "cmd": active_cmd})

    if bool(getattr(args, "run_special_cases", False)):
        special_scope = "smoke_only" if mode == "smoke" else "smoke_then_full"
        special_cmd: List[str] = [
            sys.executable,
            "tools/run_special_case_pipeline.py",
            "--date-tag",
            date_tag,
            "--domains",
            str(args.special_case_domains),
            "--run-scope",
            special_scope,
            "--strict-fail-fast" if bool(args.special_case_strict_fail_fast) else "--no-strict-fail-fast",
            "--policy-json",
            str(args.special_case_policy_json),
            "--metal-sources-csv",
            str(args.special_case_metal_sources_csv),
            "--dna-sources-csv",
            str(args.special_case_dna_sources_csv),
            "--membrane-sources-csv",
            str(args.special_case_membrane_sources_csv),
            "--skip-core-gate",
            "--strict-summary-json",
            str(strict_summary_json_path),
            "--out-prefix",
            paths["special_case_prefix"],
        ]
        commands.append({"name": "run_special_case_pipeline", "cmd": special_cmd})

    if bool(getattr(args, "run_experiment_dashboard", True)):
        dash_cmd: List[str] = [
            sys.executable,
            "tools/visualize_experiment_dashboard.py",
            "--csv",
            paths["feature_csv"],
            "--gate-json",
            str(strict_summary_json_path),
            "--metrics",
            str(args.dashboard_metrics),
            "--max-metrics",
            str(int(args.dashboard_max_metrics)),
            "--max-rows",
            str(int(args.dashboard_max_rows)),
            "--max-pdb",
            str(int(args.dashboard_max_pdb)),
            "--target-col",
            str(args.dashboard_target_col),
            "--title",
            str(args.dashboard_title).strip() or f"Nightly MD Experiment Dashboard ({date_tag})",
            "--out-html",
            paths["dashboard_html"],
            "--out-json",
            paths["dashboard_json"],
        ]
        if dashboard_compare_csv_path and os.path.exists(dashboard_compare_csv_path):
            dash_cmd.extend(["--compare-csv", dashboard_compare_csv_path])
        if dashboard_external_pdb_glob:
            dash_cmd.extend(["--pdb-glob", dashboard_external_pdb_glob])
        if dashboard_internal_pdb_glob:
            dash_cmd.extend(["--pdb-glob", dashboard_internal_pdb_glob])
        for target_name in dashboard_target_filters:
            dash_cmd.extend(["--target", target_name])
        commands.append({"name": "build_experiment_dashboard", "cmd": dash_cmd})

    commands.append({"name": "classify_runs", "cmd": [sys.executable, "tools/classify_runs_files.py"]})

    results: List[Dict[str, Any]] = []
    first_failed: Optional[int] = None
    for idx, spec in enumerate(commands, start=1):
        cmd = list(spec.get("cmd", []))
        name = str(spec.get("name", f"step_{idx}"))
        rec = _run_cmd(cmd, env=env, dry_run=bool(args.dry_run))
        rec["index"] = idx
        rec["name"] = name

        if bool(rec.get("ok", False)) and (not bool(args.dry_run)):
            if name == "rebench":
                long_status = _collect_long_stability_status(paths)
                baseline_gate = bool(long_status.get("baseline_gate_pass", False))
                if long_stability_gate_policy == "strict":
                    if not baseline_gate:
                        rec["ok"] = False
                        rec["returncode"] = int(rec.get("returncode", 2) or 2)
                        rec["gate_failure"] = "baseline_long_stability_gate_strict"
                else:
                    if (not baseline_gate) and (not bool(args.run_tuned_long_stability)):
                        rec["ok"] = False
                        rec["returncode"] = int(rec.get("returncode", 2) or 2)
                        rec["gate_failure"] = "baseline_long_stability_gate_pragmatic_no_fallback"

            if name == "tuned_long_stability_fallback":
                long_status = _collect_long_stability_status(paths)
                tuned_gate = bool(long_status.get("tuned_gate_pass", False))
                if (long_stability_gate_policy == "pragmatic") and (not tuned_gate):
                    rec["ok"] = False
                    rec["returncode"] = int(rec.get("returncode", 2) or 2)
                    rec["gate_failure"] = "tuned_long_stability_gate_pragmatic"

        results.append(rec)
        if (not rec.get("ok", False)) and (first_failed is None):
            first_failed = idx
            if bool(args.fail_fast):
                break

    claim_status = _collect_claim_status(paths)
    long_stability_status = _collect_long_stability_status(paths)
    ood_status = _collect_ood_status(paths)
    ood_measured20_status = _collect_ood_status({"ood_summary_json": paths["ood_measured20_summary_json"]})
    ood_measured40_status = _collect_ood_status({"ood_summary_json": paths["ood_measured40_summary_json"]})
    active_learning_status = _collect_active_learning_status(paths)
    active_learning_live_unseen_hardcase_status = _collect_live_unseen_hardcase_status(paths)
    active_learning_priority_status = _collect_active_learning_priority_status(paths)
    active_learning_priority_ab_status = _collect_active_learning_priority_ab_status(paths)
    dashboard_status = _collect_dashboard_status(paths)
    commercial_readiness_status = _collect_commercial_readiness_status(paths)
    special_case_status = _collect_special_case_status(paths)
    attempts_csv_links = _resolve_attempts_csv_links(str(args.runs_dir), date_tag)
    initial_claim_requirement_failed = False
    if bool(getattr(args, "claim_require_initial_ready", True)) and (not bool(args.dry_run)):
        initial_ready = claim_status.get("initial_claim_ready_for_allatom", None)
        if initial_ready is False:
            initial_claim_requirement_failed = True
            if first_failed is None:
                run_claim_rec = next((r for r in results if str(r.get("name", "")) == "run_claim_readiness"), None)
                first_failed = int(run_claim_rec.get("index", len(results) or 1)) if run_claim_rec else int(len(results) or 1)

    measured_proxy_requirement_failed = False
    measured_proxy_failures: List[Dict[str, Any]] = []
    if not bool(args.dry_run):
        if bool(getattr(args, "run_ood_measured20", False)):
            proxy20 = int(ood_measured20_status.get("proxy_rows_added", 0) or 0)
            if proxy20 > 0:
                measured_proxy_requirement_failed = True
                measured_proxy_failures.append({"stage": "ood_measured20_gate", "proxy_rows_added": proxy20})
                if first_failed is None:
                    rec20 = next((r for r in results if str(r.get("name", "")) == "ood_measured20_gate"), None)
                    first_failed = int(rec20.get("index", len(results) or 1)) if rec20 else int(len(results) or 1)
        if bool(getattr(args, "run_ood_measured40", False)):
            proxy40 = int(ood_measured40_status.get("proxy_rows_added", 0) or 0)
            if proxy40 > 0:
                measured_proxy_requirement_failed = True
                measured_proxy_failures.append({"stage": "ood_measured40_gate", "proxy_rows_added": proxy40})
                if first_failed is None:
                    rec40 = next((r for r in results if str(r.get("name", "")) == "ood_measured40_gate"), None)
                    first_failed = int(rec40.get("index", len(results) or 1)) if rec40 else int(len(results) or 1)

    dashboard_metrics_requirement_failed = False
    if bool(getattr(args, "run_experiment_dashboard", True)) and (not bool(args.dry_run)):
        metrics_count = int(dashboard_status.get("metrics_count", 0) or 0)
        if metrics_count <= 0:
            dashboard_metrics_requirement_failed = True
            if first_failed is None:
                rec_dash = next((r for r in results if str(r.get("name", "")) == "build_experiment_dashboard"), None)
                first_failed = int(rec_dash.get("index", len(results) or 1)) if rec_dash else int(len(results) or 1)

    passed = (
        bool(first_failed is None)
        and (not initial_claim_requirement_failed)
        and (not measured_proxy_requirement_failed)
        and (not dashboard_metrics_requirement_failed)
    )
    summary = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "date_tag": date_tag,
        "mode": mode,
        "long_stability_gate_policy": long_stability_gate_policy,
        "skip_speed_rebench": bool(getattr(args, "skip_speed_rebench", False)),
        "targets": str(args.targets),
        "dry_run": bool(args.dry_run),
        "pass": bool(passed),
        "failed_step_index": first_failed,
        "total_steps": int(len(commands)),
        "executed_steps": int(len(results)),
        "long_stability_status": long_stability_status,
        "ood_status": ood_status,
        "ood_measured20_status": ood_measured20_status,
        "ood_measured40_status": ood_measured40_status,
        "active_learning_status": active_learning_status,
        "active_learning_live_unseen_hardcase_status": active_learning_live_unseen_hardcase_status,
        "active_learning_priority_status": active_learning_priority_status,
        "active_learning_priority_ab_status": active_learning_priority_ab_status,
        "dashboard_status": dashboard_status,
        "commercial_readiness_status": commercial_readiness_status,
        "special_case_status": special_case_status,
        "claim_status": claim_status,
        "claim_profile": claim_profile_status,
        "feature_profile": feature_profile_status,
        "rebench_ai_runtime_mode_status": rebench_runtime_mode_status,
        "attempts_csv_links": attempts_csv_links,
        "speed_profile_defaults": {
            "json": str(getattr(args, "speed_profile_defaults_json", "")).strip(),
            "section": str(getattr(args, "speed_profile_defaults_section", "nightly")).strip()
            or "nightly",
            "resolved": resolved_speed_profile,
        },
        "claim_require_initial_ready": bool(getattr(args, "claim_require_initial_ready", True)),
        "initial_claim_requirement_failed": bool(initial_claim_requirement_failed),
        "measured_proxy_requirement_failed": bool(measured_proxy_requirement_failed),
        "measured_proxy_failures": measured_proxy_failures,
        "dashboard_metrics_requirement_failed": bool(dashboard_metrics_requirement_failed),
        "preflight_status": preflight_status,
        "resolved_inputs": {
            **resolved_inputs,
        },
        "paths": paths,
        "claim_accuracy_csv": claim_accuracy_csv,
        "results": results,
        "ood_dual_report_status": {},
    }

    with open(paths["batch_summary_json"], "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    lines = [
        "# Nightly Screening Batch",
        "",
        f"- date_tag: {date_tag}",
        f"- mode: {mode}",
        f"- long_stability_gate_policy: {long_stability_gate_policy}",
        f"- skip_speed_rebench: {bool(getattr(args, 'skip_speed_rebench', False))}",
        f"- claim_accuracy_csv: {claim_accuracy_csv}",
        f"- dry_run: {bool(args.dry_run)}",
        f"- pass: {bool(passed)}",
        f"- executed_steps: {len(results)}/{len(commands)}",
        f"- preflight_pass: {bool(preflight_status.get('pass', False))}",
    ]
    if long_stability_status:
        if "baseline_gate_pass" in long_stability_status:
            lines.append(f"- baseline_long_stability_gate_pass: {long_stability_status['baseline_gate_pass']}")
        if "tuned_gate_pass" in long_stability_status:
            lines.append(f"- tuned_long_stability_gate_pass: {long_stability_status['tuned_gate_pass']}")
        if "tuned_failed_targets" in long_stability_status:
            lines.append(f"- tuned_long_stability_failed_targets: {long_stability_status['tuned_failed_targets']}")
    if ood_status:
        if "pass" in ood_status:
            lines.append(f"- ood_gate_pass: {ood_status['pass']}")
        if "paired_targets" in ood_status:
            lines.append(f"- ood_paired_targets: {ood_status['paired_targets']}")
        if "avg_pair_rmsd_aligned_A" in ood_status:
            lines.append(f"- ood_avg_pair_rmsd_aligned_A: {ood_status['avg_pair_rmsd_aligned_A']}")
        if "proxy_rows_added" in ood_status:
            lines.append(f"- ood_proxy_rows_added: {ood_status['proxy_rows_added']}")
    if ood_measured20_status:
        if "pass" in ood_measured20_status:
            lines.append(f"- ood_measured20_gate_pass: {ood_measured20_status['pass']}")
        if "paired_targets" in ood_measured20_status:
            lines.append(f"- ood_measured20_paired_targets: {ood_measured20_status['paired_targets']}")
        if "avg_pair_rmsd_aligned_A" in ood_measured20_status:
            lines.append(
                f"- ood_measured20_avg_pair_rmsd_aligned_A: {ood_measured20_status['avg_pair_rmsd_aligned_A']}"
            )
        if "proxy_rows_added" in ood_measured20_status:
            lines.append(f"- ood_measured20_proxy_rows_added: {ood_measured20_status['proxy_rows_added']}")
        if "domain_coverage" in ood_measured20_status:
            lines.append(f"- ood_measured20_domain_coverage: {ood_measured20_status['domain_coverage']}")
        if "real_pair_coverage" in ood_measured20_status:
            lines.append(f"- ood_measured20_real_pair_coverage: {ood_measured20_status['real_pair_coverage']}")
    if ood_measured40_status:
        if "pass" in ood_measured40_status:
            lines.append(f"- ood_measured40_gate_pass: {ood_measured40_status['pass']}")
        if "paired_targets" in ood_measured40_status:
            lines.append(f"- ood_measured40_paired_targets: {ood_measured40_status['paired_targets']}")
        if "avg_pair_rmsd_aligned_A" in ood_measured40_status:
            lines.append(
                f"- ood_measured40_avg_pair_rmsd_aligned_A: {ood_measured40_status['avg_pair_rmsd_aligned_A']}"
            )
        if "proxy_rows_added" in ood_measured40_status:
            lines.append(f"- ood_measured40_proxy_rows_added: {ood_measured40_status['proxy_rows_added']}")
        if "domain_coverage" in ood_measured40_status:
            lines.append(f"- ood_measured40_domain_coverage: {ood_measured40_status['domain_coverage']}")
        if "real_pair_coverage" in ood_measured40_status:
            lines.append(f"- ood_measured40_real_pair_coverage: {ood_measured40_status['real_pair_coverage']}")
    if active_learning_priority_status:
        if "priority_targets_count" in active_learning_priority_status:
            lines.append(
                f"- active_learning_priority_targets_count: {active_learning_priority_status['priority_targets_count']}"
            )
        if "ood_selected" in active_learning_priority_status:
            lines.append(f"- active_learning_priority_ood_selected: {active_learning_priority_status['ood_selected']}")
        if "oversize_selected" in active_learning_priority_status:
            lines.append(
                f"- active_learning_priority_oversize_selected: {active_learning_priority_status['oversize_selected']}"
            )
        if "feature_selected" in active_learning_priority_status:
            lines.append(
                f"- active_learning_priority_feature_selected: {active_learning_priority_status['feature_selected']}"
            )
    if active_learning_priority_ab_status:
        if "jaccard" in active_learning_priority_ab_status:
            lines.append(f"- active_learning_priority_ab_jaccard: {active_learning_priority_ab_status['jaccard']}")
        if "added_in_candidate_count" in active_learning_priority_ab_status:
            lines.append(
                "- active_learning_priority_ab_added_in_candidate_count: "
                f"{active_learning_priority_ab_status['added_in_candidate_count']}"
            )
        if "ood_coverage_delta" in active_learning_priority_ab_status:
            lines.append(
                f"- active_learning_priority_ab_ood_coverage_delta: {active_learning_priority_ab_status['ood_coverage_delta']}"
            )
    if active_learning_live_unseen_hardcase_status:
        if "pass" in active_learning_live_unseen_hardcase_status:
            lines.append(
                f"- active_learning_live_unseen_hardcase_pass: {active_learning_live_unseen_hardcase_status['pass']}"
            )
        if "rows_total" in active_learning_live_unseen_hardcase_status:
            lines.append(
                "- active_learning_live_unseen_hardcase_rows_total: "
                f"{active_learning_live_unseen_hardcase_status['rows_total']}"
            )
        if "selected_targets_count" in active_learning_live_unseen_hardcase_status:
            lines.append(
                "- active_learning_live_unseen_hardcase_selected_targets_count: "
                f"{active_learning_live_unseen_hardcase_status['selected_targets_count']}"
            )
        if "used_fallback_all_targets" in active_learning_live_unseen_hardcase_status:
            lines.append(
                "- active_learning_live_unseen_hardcase_used_fallback_all_targets: "
                f"{active_learning_live_unseen_hardcase_status['used_fallback_all_targets']}"
            )
    if active_learning_status:
        if "pass" in active_learning_status:
            lines.append(f"- active_learning_pass: {active_learning_status['pass']}")
        if "hard_mining_selected_targets_count" in active_learning_status:
            lines.append(
                f"- active_learning_hard_mining_selected_targets_count: "
                f"{active_learning_status['hard_mining_selected_targets_count']}"
            )
        if "hard_mining_selected_targets" in active_learning_status:
            lines.append(
                f"- active_learning_hard_mining_selected_targets: "
                f"{active_learning_status['hard_mining_selected_targets']}"
            )
        if "curriculum_pass" in active_learning_status:
            lines.append(f"- active_learning_curriculum_pass: {active_learning_status['curriculum_pass']}")
        if "claim_pass" in active_learning_status:
            lines.append(f"- active_learning_claim_pass: {active_learning_status['claim_pass']}")
    if dashboard_status:
        if "run_count" in dashboard_status:
            lines.append(f"- dashboard_run_count: {dashboard_status['run_count']}")
        if "metrics_count" in dashboard_status:
            lines.append(f"- dashboard_metrics_count: {dashboard_status['metrics_count']}")
        if "pdb_count" in dashboard_status:
            lines.append(f"- dashboard_pdb_count: {dashboard_status['pdb_count']}")
        if "target_filters" in dashboard_status:
            lines.append(f"- dashboard_target_filters: {dashboard_status['target_filters']}")
    if commercial_readiness_status:
        if "readiness_score" in commercial_readiness_status:
            lines.append(f"- commercial_readiness_score: {commercial_readiness_status['readiness_score']}")
        if "readiness_tier" in commercial_readiness_status:
            lines.append(f"- commercial_readiness_tier: {commercial_readiness_status['readiness_tier']}")
        if "failed_checks" in commercial_readiness_status:
            lines.append(f"- commercial_readiness_failed_checks: {commercial_readiness_status['failed_checks']}")
        if "critical_checks_pass" in commercial_readiness_status:
            lines.append(
                f"- commercial_readiness_critical_checks_pass: {commercial_readiness_status['critical_checks_pass']}"
            )
    if special_case_status:
        if "pass" in special_case_status:
            lines.append(f"- special_case_pass: {special_case_status['pass']}")
        if "failed_stage" in special_case_status:
            lines.append(f"- special_case_failed_stage: {special_case_status['failed_stage']}")
        if "stage_pass" in special_case_status:
            lines.append(f"- special_case_stage_pass: {special_case_status['stage_pass']}")
    if claim_status:
        if "initial_claim_ready_for_allatom" in claim_status:
            lines.append(f"- initial_claim_ready_for_allatom: {claim_status['initial_claim_ready_for_allatom']}")
        if "initial_claim_failed_metrics" in claim_status:
            lines.append(f"- initial_claim_failed_metrics: {claim_status['initial_claim_failed_metrics']}")
        if "corrected_claim_failed_metrics" in claim_status:
            lines.append(f"- corrected_claim_failed_metrics: {claim_status['corrected_claim_failed_metrics']}")
        if "corrected_claim_ready_for_allatom" in claim_status:
            lines.append(
                f"- corrected_claim_ready_for_allatom: {claim_status['corrected_claim_ready_for_allatom']}"
            )
    lines.append(f"- claim_profile_json: {claim_profile_status.get('path')}")
    lines.append(f"- claim_profile_loaded: {claim_profile_status.get('loaded')}")
    lines.append(f"- claim_profile_keys_applied: {claim_profile_status.get('keys_applied')}")
    lines.append(f"- feature_profile_json: {feature_profile_status.get('path')}")
    lines.append(f"- feature_profile_loaded: {feature_profile_status.get('loaded')}")
    lines.append(f"- feature_profile_keys_applied: {feature_profile_status.get('keys_applied')}")
    lines.append(
        f"- accuracy_revalidation_attempts_csv: {attempts_csv_links.get('accuracy_revalidation_attempts_csv', '')}"
    )
    lines.append(
        f"- post_gate_pipeline_attempts_csv: {attempts_csv_links.get('post_gate_pipeline_attempts_csv', '')}"
    )
    lines.append(
        f"- speed_profile_defaults_json: {str(getattr(args, 'speed_profile_defaults_json', '')).strip()}"
    )
    lines.append(
        f"- speed_profile_defaults_section: {str(getattr(args, 'speed_profile_defaults_section', 'nightly')).strip() or 'nightly'}"
    )
    lines.append(f"- resolved_speed_profile: {resolved_speed_profile}")
    lines.append(f"- rebench_ai_runtime_mode_status: {rebench_runtime_mode_status}")
    lines.append(f"- rebench_ai_runtime_profile_json: {paths.get('rebench_ai_runtime_profile_json')}")
    lines.append(f"- rebench_ai_runtime_profile_csv: {paths.get('rebench_ai_runtime_profile_csv')}")
    lines.append(f"- claim_require_initial_ready: {bool(getattr(args, 'claim_require_initial_ready', True))}")
    lines.append(f"- initial_claim_requirement_failed: {bool(initial_claim_requirement_failed)}")
    lines.append(f"- measured_proxy_requirement_failed: {bool(measured_proxy_requirement_failed)}")
    lines.append(f"- measured_proxy_failures: {measured_proxy_failures}")
    lines.append(f"- dashboard_metrics_requirement_failed: {bool(dashboard_metrics_requirement_failed)}")
    lines.append(f"- failure_latest_json: {paths.get('failure_latest_json')}")
    lines.append(f"- failure_latest_md: {paths.get('failure_latest_md')}")
    lines.append(f"- dashboard_external_pdb_glob: {dashboard_external_pdb_glob}")
    lines.append(f"- dashboard_internal_pdb_glob: {dashboard_internal_pdb_glob}")
    lines.append(f"- dashboard_include_internal_pdb: {bool(dashboard_include_internal_pdb)}")
    lines.append(f"- dashboard_internal_pdb_dir: {dashboard_internal_pdb_dir}")
    lines.append(f"- dashboard_html: {paths.get('dashboard_html')}")
    lines.append(f"- dashboard_json: {paths.get('dashboard_json')}")
    lines.append(f"- ood_dual_report_json: {paths.get('ood_dual_report_json')}")
    lines.append(f"- ood_dual_report_md: {paths.get('ood_dual_report_md')}")
    lines.append(f"- external_packet_json: {paths.get('external_packet_json')}")
    lines.append(f"- commercial_readiness_json: {paths.get('commercial_readiness_json')}")
    lines.append(f"- commercial_readiness_csv: {paths.get('commercial_readiness_csv')}")
    lines.append(f"- commercial_readiness_md: {paths.get('commercial_readiness_md')}")
    lines.append(f"- repro_snapshot_json: {paths.get('repro_snapshot_json')}")
    lines.append(f"- maintenance_summary_json: {paths.get('maintenance_summary_json')}")
    if first_failed is not None:
        lines.append(f"- failed_step_index: {first_failed}")
    lines.append("")
    lines.append("## Steps")
    for rec in results:
        lines.append(
            f"- [{rec.get('index')}] rc={rec.get('returncode')} ok={rec.get('ok')} : {rec.get('cmd_str')}"
        )
    with open(paths["batch_summary_md"], "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    summary["failure_latest_report"] = _write_failure_latest_report(summary, paths)
    ood_dual_report_status = _run_ood_dual_report(
        args=args,
        paths=paths,
        env=env,
        date_tag=date_tag,
    )
    summary["ood_dual_report_status"] = ood_dual_report_status
    external_packet_status = _run_external_packet(
        args=args,
        paths=paths,
        env=env,
        external_packet_accuracy_external_csv_path=external_packet_accuracy_external_csv_path,
    )
    summary["external_packet_status"] = external_packet_status
    commercial_readiness_report_status = _run_commercial_readiness(
        args=args,
        paths=paths,
        env=env,
        external_packet_accuracy_external_csv_path=external_packet_accuracy_external_csv_path,
    )
    summary["commercial_readiness_report_status"] = commercial_readiness_report_status
    summary["commercial_readiness_status"] = _collect_commercial_readiness_status(paths)
    external_submission_status = _publish_external_submission(args=args, paths=paths)
    summary["external_submission_status"] = external_submission_status
    summary["maintenance"] = _run_runs_maintenance(args, paths)

    post_failures: List[Dict[str, Any]] = []
    if bool(ood_dual_report_status.get("requested", False)) and (not bool(ood_dual_report_status.get("ok", True))):
        post_failures.append(
            {
                "name": "ood_dual_report",
                "returncode": int(ood_dual_report_status.get("returncode", 2) or 2),
                "reason": "ood_dual_report_failed",
                "gate_failure": ood_dual_report_status.get("gate_failure"),
            }
        )
    if bool(external_packet_status.get("requested", False)) and (not bool(external_packet_status.get("ok", True))):
        post_failures.append(
            {
                "name": "external_packet",
                "returncode": int(external_packet_status.get("returncode", 2) or 2),
                "reason": "packet_build_failed",
            }
        )
    if bool(commercial_readiness_report_status.get("requested", False)) and (
        not bool(commercial_readiness_report_status.get("ok", True))
    ):
        post_failures.append(
            {
                "name": "commercial_readiness_report",
                "returncode": int(commercial_readiness_report_status.get("returncode", 2) or 2),
                "reason": "commercial_readiness_report_failed",
                "gate_failure": commercial_readiness_report_status.get("gate_failure"),
            }
        )
    if bool(external_submission_status.get("requested", False)) and (not bool(external_submission_status.get("ok", True))):
        post_failures.append(
            {
                "name": "external_submission",
                "returncode": 2,
                "reason": "submission_publish_failed",
                "required_missing": external_submission_status.get("required_missing", []),
            }
        )
    summary["post_process_failures"] = post_failures
    if len(post_failures) > 0:
        summary["pass"] = False
        if summary.get("failed_step_index") is None:
            summary["failed_step_index"] = int(len(commands) + 1)

    summary["reproducibility_snapshot"] = _write_reproducibility_snapshot(
        args=args,
        paths=paths,
        summary=summary,
        resolved_inputs=resolved_inputs,
        env=env,
    )

    with open(paths["batch_summary_json"], "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    return summary


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Run nightly 2-bead screening + feature collection + claim-readiness chain."
    )
    p.add_argument("--date-tag", type=str, default="")
    p.add_argument("--mode", type=str, default="smoke", choices=["smoke", "full"])
    p.add_argument("--targets", type=str, default="all")
    p.add_argument("--runs-dir", type=str, default="runs")
    p.add_argument("--public-out-dir", type=str, default="data/public_structures/nightly")
    p.add_argument("--sources-csv", type=str, default="config/structure_sources_10targets.csv")
    p.add_argument("--afdb-model-versions", type=str, default="v6,v5,v4")
    p.add_argument("--external-manifest", type=str, default="runs/real_md_source_manifest_openmm_2bead_2026-02-17.csv")
    p.add_argument(
        "--strict-summary-json",
        type=str,
        default="runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_summary.json",
    )
    p.add_argument(
        "--accuracy-external-csv",
        type=str,
        default="runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_accuracy_external.csv",
    )
    p.add_argument(
        "--claim-accuracy-csv",
        type=str,
        default="",
        help=(
            "Optional accuracy CSV for claim steps. "
            "When empty, uses nightly rebench output: <rebench_prefix>_accuracy.csv."
        ),
    )
    p.add_argument(
        "--claim-policy-json",
        type=str,
        default="config/allatom_equivalence_acceptance_v1_2026-02-17.json",
    )
    p.add_argument(
        "--claim-profile-json",
        type=str,
        default="config/claim_input_profile_accuracy_v1_2026-02-19.json",
    )
    p.add_argument(
        "--feature-profile-json",
        type=str,
        default="config/feature_control_perturbation_profile_v1_2026-02-22.json",
    )
    p.add_argument(
        "--long-stability-gate-policy",
        type=str,
        default="strict",
        choices=["strict", "pragmatic"],
    )
    p.add_argument("--run-tuned-long-stability", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument(
        "--rebench-stability-profile-json",
        type=str,
        default="config/long_stability_target_tuned_all10_2026-02-17_v2.json",
    )
    p.add_argument(
        "--tuned-long-stability-profile-json",
        type=str,
        default="config/long_stability_target_tuned_all10_2026-02-17_v2.json",
    )
    p.add_argument("--run-ood-gate", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--ood-strict-fail", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--ood-enable-proxy-manifest", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--ood-require-real-afdb", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--ood-max-proxy-rows", type=int, default=0)
    p.add_argument("--ood-enable-windowed-match", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--ood-min-pairs", type=int, default=8)
    p.add_argument("--ood-max-mean-pair-rmsd", type=float, default=6.0)
    p.add_argument("--ood-max-length-ratio", type=float, default=1.5)
    p.add_argument("--ood-max-windowed-rmsd", type=float, default=12.0)
    p.add_argument("--run-ood-dual-report", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--ood-dual-report-enforce-pass", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--ood-robust-enable-proxy-manifest", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--ood-robust-enable-windowed-match", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--ood-robust-max-mean-pair-rmsd", type=float, default=6.0)
    p.add_argument("--ood-robust-max-windowed-rmsd", type=float, default=8.0)
    p.add_argument("--ood-robust-strict-fail", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--run-ood-measured20", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument(
        "--ood-measured20-targets",
        type=str,
        default="sources_all",
        help="Target selector for measured20 OOD run. Use sources_all to resolve targets from measured20 sources CSV.",
    )
    p.add_argument("--ood-measured20-sources-csv", type=str, default="config/structure_sources_ood_measured20_v1.csv")
    p.add_argument("--ood-measured20-tags-csv", type=str, default="config/structure_sources_ood_measured20_tags_v1.csv")
    p.add_argument("--ood-measured20-min-domain-coverage", type=int, default=0)
    p.add_argument("--ood-measured20-min-pairs", type=int, default=16)
    p.add_argument("--ood-measured20-max-mean-rmsd", type=float, default=6.0)
    p.add_argument("--ood-measured20-max-proxy-rows", type=int, default=0)
    p.add_argument("--ood-measured20-require-real-afdb", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--ood-measured20-enable-proxy-manifest", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--ood-measured20-strict-fail", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--run-ood-measured40", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument(
        "--ood-measured40-targets",
        type=str,
        default="sources_all",
        help="Target selector for measured40 OOD run. Use sources_all to resolve targets from measured40 sources CSV.",
    )
    p.add_argument("--ood-measured40-sources-csv", type=str, default="config/structure_sources_ood_measured40_v1.csv")
    p.add_argument("--ood-measured40-tags-csv", type=str, default="config/structure_sources_ood_measured40_tags_v1.csv")
    p.add_argument("--ood-measured40-min-domain-coverage", type=int, default=4)
    p.add_argument("--ood-measured40-min-pairs", type=int, default=24)
    p.add_argument("--ood-measured40-max-mean-rmsd", type=float, default=6.0)
    p.add_argument("--ood-measured40-max-proxy-rows", type=int, default=0)
    p.add_argument("--ood-measured40-require-real-afdb", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--ood-measured40-enable-proxy-manifest", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--ood-measured40-strict-fail", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--claim-require-initial-ready", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--run-claim-correction", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--claim-correction-enforce-ready", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--claim-correction-max-iters", type=int, default=10)
    p.add_argument("--claim-correction-target-margin", type=float, default=0.9)
    p.add_argument("--claim-correction-damping", type=float, default=0.75)
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
    p.add_argument("--run-active-learning", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--active-learning-dry-run", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--active-learning-topk", type=int, default=4)
    p.add_argument("--active-learning-priority-enabled", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--active-learning-priority-ood-pair-csv", type=str, default="")
    p.add_argument("--active-learning-priority-ood-min-rmsd", type=float, default=8.0)
    p.add_argument("--active-learning-priority-ood-topk", type=int, default=8)
    p.add_argument(
        "--active-learning-priority-oversize-csv",
        type=str,
        default="runs/live_unseen_failure_breakdown_rolling.csv",
    )
    p.add_argument("--active-learning-priority-oversize-topk", type=int, default=8)
    p.add_argument("--active-learning-priority-oversize-target-col", type=str, default="source_target")
    p.add_argument("--active-learning-priority-feature-csv", type=str, default="")
    p.add_argument("--active-learning-priority-feature-topk", type=int, default=8)
    p.add_argument("--active-learning-priority-feature-target-col", type=str, default="target")
    p.add_argument("--active-learning-priority-feature-rmsd-col", type=str, default="auto")
    p.add_argument("--active-learning-priority-feature-violations-col", type=str, default="auto")
    p.add_argument("--active-learning-priority-feature-control-prefix", type=str, default="control_")
    p.add_argument("--active-learning-priority-feature-min-control-levels", type=float, default=2.0)
    p.add_argument("--active-learning-priority-bonus", type=float, default=1.0)
    p.add_argument(
        "--active-learning-stage2-csv",
        type=str,
        default="runs/accuracy_gate_fast_opt_2026-02-18_stage2.csv",
        help="Fallback stage2 csv for active-learning hard-mining when nightly rebench stage2 is absent.",
    )
    p.add_argument(
        "--active-learning-curriculum-base-manifest-csv",
        type=str,
        default="runs/distilled_residual_manifest_repaired_fp32_cap100.csv",
    )
    p.add_argument("--active-learning-curriculum-hardcase-manifest-csv", type=str, default="")
    p.add_argument("--active-learning-auto-hardcase-from-live-unseen", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument(
        "--active-learning-live-unseen-manifest-csv",
        type=str,
        default="runs/distilled_residual_manifest_live_unseen.csv",
    )
    p.add_argument(
        "--active-learning-live-unseen-failure-breakdown-csv",
        type=str,
        default="runs/live_unseen_failure_breakdown_rolling.csv",
    )
    p.add_argument("--active-learning-live-unseen-hardcase-max-targets", type=int, default=32)
    p.add_argument("--active-learning-live-unseen-hardcase-min-fail-count", type=float, default=1.0)
    p.add_argument("--active-learning-curriculum-checkpoint-dir", type=str, default="models/curriculum_active_learning")
    p.add_argument("--active-learning-curriculum-max-targets", type=int, default=0)
    p.add_argument("--active-learning-curriculum-skip-manifest-build", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--active-learning-skip-curriculum-training", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--active-learning-skip-claim-correction", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--active-learning-claim-max-iters", type=int, default=10)
    p.add_argument("--active-learning-claim-target-margin", type=float, default=0.9)
    p.add_argument("--active-learning-claim-damping", type=float, default=0.75)
    p.add_argument("--active-learning-claim-enforce-complete", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--run-special-cases", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--special-case-domains", type=str, default="metal,dna,membrane")
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
    p.add_argument("--special-case-strict-fail-fast", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--feature-enable-control-perturbation", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--feature-control-perturbation-seed", type=int, default=20260222)
    p.add_argument("--feature-perturb-ionic-strength-grid", type=str, default="0.05,0.15,0.30,0.50")
    p.add_argument("--feature-perturb-ptm-count-grid", type=str, default="0,1,2,3")
    p.add_argument("--feature-perturb-temperature-end-grid", type=str, default="300,350,400,500")
    p.add_argument("--feature-perturb-hydro-scale-grid", type=str, default="0.8,1.0,1.2")
    p.add_argument("--feature-perturb-force-scale-mult-grid", type=str, default="0.9,1.0,1.1")
    p.add_argument("--feature-control-prefix", type=str, default="control_")
    p.add_argument("--feature-observed-prefix", type=str, default="observed_")
    p.add_argument(
        "--run-experiment-dashboard",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Build interactive experiment dashboard (HTML/JSON) from nightly feature CSV + fetched PDBs.",
    )
    p.add_argument(
        "--dashboard-compare-csv",
        type=str,
        default="",
        help="Optional explicit compare CSV. If empty, most recent previous nightly feature CSV is auto-linked.",
    )
    p.add_argument("--dashboard-pdb-glob", type=str, default="")
    p.add_argument(
        "--dashboard-include-internal-pdb",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Include internally postprocessed PDB snapshots in dashboard 3D viewer together with public structures.",
    )
    p.add_argument(
        "--dashboard-internal-pdb-dir",
        type=str,
        default="",
        help="Directory where collect_feature_matrix exports internal postprocessed PDB files.",
    )
    p.add_argument(
        "--dashboard-internal-pdb-glob",
        type=str,
        default="",
        help="Optional explicit glob for internal postprocessed PDB files. Overrides --dashboard-internal-pdb-dir.",
    )
    p.add_argument(
        "--dashboard-internal-pdb-per-target",
        type=int,
        default=1,
        help="How many internal postprocessed PDB snapshots to export per target during feature collection.",
    )
    p.add_argument("--dashboard-target-col", type=str, default="target")
    p.add_argument("--dashboard-metrics", type=str, default="auto")
    p.add_argument("--dashboard-max-metrics", type=int, default=12)
    p.add_argument("--dashboard-max-rows", type=int, default=2000)
    p.add_argument("--dashboard-max-pdb", type=int, default=12)
    p.add_argument("--dashboard-title", type=str, default="")
    p.add_argument("--run-external-packet", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--external-packet-version", type=str, choices=["v1", "v2", "v3"], default="v3")
    p.add_argument(
        "--external-packet-gate-json",
        type=str,
        default="runs/accuracy_gate_arch_focus_2026-02-19.json",
    )
    p.add_argument(
        "--external-packet-parity-target-csv",
        type=str,
        default="runs/accuracy_gate_arch_focus_2026-02-19_parity_target.csv",
    )
    p.add_argument(
        "--external-packet-stage2-csv",
        type=str,
        default="runs/accuracy_gate_arch_focus_2026-02-19_stage2.csv",
    )
    p.add_argument(
        "--external-packet-fidelity-csv",
        type=str,
        default="runs/physics_fidelity_report.csv",
    )
    p.add_argument("--external-packet-accuracy-external-csv", type=str, default="")
    p.add_argument("--external-packet-quality-curation-csv", type=str, default="")
    p.add_argument("--external-packet-reproducibility-json", type=str, default="")
    p.add_argument("--external-packet-baseline-config-json", type=str, default="")
    p.add_argument("--external-packet-strict-optional-sources", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--run-commercial-readiness", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--commercial-readiness-nightly-summary-json", type=str, default="")
    p.add_argument("--commercial-readiness-strict-summary-json", type=str, default="")
    p.add_argument("--commercial-readiness-dashboard-json", type=str, default="")
    p.add_argument("--commercial-readiness-external-packet-json", type=str, default="")
    p.add_argument("--commercial-readiness-stage2-csv", type=str, default="")
    p.add_argument("--commercial-readiness-trajectory-target-tail-csv", type=str, default="")
    p.add_argument("--commercial-readiness-accuracy-external-csv", type=str, default="")
    p.add_argument("--commercial-readiness-feature-csv", type=str, default="")
    p.add_argument(
        "--commercial-readiness-strict-source-policy",
        type=str,
        default="full_only",
        choices=["full_only", "prefer_full", "any"],
    )
    p.add_argument("--commercial-readiness-speedup-threshold", type=float, default=12.0)
    p.add_argument("--commercial-readiness-speedup-p95-threshold", type=float, default=12.0)
    p.add_argument("--commercial-readiness-speedup-worst-threshold", type=float, default=12.0)
    p.add_argument("--commercial-readiness-traj-fps-p05-threshold", type=float, default=60.0)
    p.add_argument("--commercial-readiness-traj-fps-worst-threshold", type=float, default=60.0)
    p.add_argument("--commercial-readiness-max-rmsd-p95-a", type=float, default=8.0)
    p.add_argument("--commercial-readiness-max-rmsd-worst-a", type=float, default=12.0)
    p.add_argument("--commercial-readiness-min-dashboard-metrics", type=int, default=3)
    p.add_argument("--commercial-readiness-min-dashboard-runs", type=int, default=1)
    p.add_argument("--commercial-readiness-min-external-targets", type=int, default=5)
    p.add_argument("--commercial-readiness-min-feature-targets", type=int, default=8)
    p.add_argument("--commercial-readiness-feature-max-missing-rate", type=float, default=0.15)
    p.add_argument("--commercial-readiness-feature-min-variable-cols", type=int, default=8)
    p.add_argument("--commercial-readiness-feature-max-constant-flag-cols", type=int, default=8)
    p.add_argument("--commercial-readiness-min-score", type=float, default=75.0)
    p.add_argument("--commercial-readiness-enforce-pass", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument(
        "--commercial-readiness-disable-auto-discovery",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    p.add_argument("--publish-external-submission", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--external-submission-root", type=str, default="runs/external_eval_submission")
    p.add_argument("--external-submission-strict", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--speed-profile-defaults-json", type=str, default="config/speed_profile_defaults.json")
    p.add_argument("--speed-profile-defaults-section", type=str, default="nightly")
    p.add_argument("--speed-mode", type=str, default="")
    p.add_argument("--speed-mode-replicas", type=int, default=-1)
    p.add_argument("--speed-profile-max-replicas", type=int, default=-1)
    p.add_argument("--rebench-use-ai-router", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument(
        "--rebench-ai-runtime-mode",
        type=str,
        default="eager",
        choices=["eager", "scripted", "compiled", "onnx"],
    )
    p.add_argument("--rebench-ai-disable-exploration", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--rebench-ai-use-hip-graph", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--rebench-ai-graph-warmup-iters", type=int, default=2)
    p.add_argument(
        "--rebench-speed-profile-preserve-runtime-mode",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Preserve selected rebench runtime mode even when speed profile preset has its own mode.",
    )
    p.add_argument("--rebench-ai-router-checkpoint", type=str, default="")
    p.add_argument("--rebench-ai-router-checkpoint-strict", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--auto-select-rebench-ai-runtime-mode", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument(
        "--rebench-ai-runtime-policy-json",
        type=str,
        default="config/release_v1_0_runtime_policy_2026-02-22.json",
    )
    p.add_argument("--rebench-ai-runtime-profile-targets", type=str, default="")
    p.add_argument("--rebench-ai-runtime-profile-modes", type=str, default="eager,scripted,compiled,onnx")
    p.add_argument("--rebench-ai-runtime-profile-steps", type=int, default=80)
    p.add_argument("--rebench-ai-runtime-profile-runs", type=int, default=1)
    p.add_argument("--rebench-ai-runtime-profile-warmup-steps", type=int, default=30)
    p.add_argument("--rebench-ai-runtime-profile-batch-replicas", type=int, default=1)
    p.add_argument("--rebench-ai-runtime-profile-ai-interval", type=int, default=4)
    p.add_argument(
        "--ai-interval",
        type=int,
        default=4,
        help="Base AI interval before speed-mode scaling (nightly speed-stable default).",
    )
    p.add_argument(
        "--target-ai-interval-policy",
        type=str,
        default="speed_opt_v2",
        help="Target-specific AI interval overrides (preset or csv/json spec).",
    )
    p.add_argument(
        "--skip-speed-rebench",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Accuracy-first mode: skip explicit speed re-benchmark stage in rebench step.",
    )
    p.add_argument("--maintenance-prune-runs", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--maintenance-keep-per-role", type=int, default=2)
    p.add_argument("--maintenance-archive-root", type=str, default="_archive_pruned")
    p.add_argument("--maintenance-compress-archive", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--maintenance-remove-uncompressed-archive", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--maintenance-protect-prefix", action="append", default=[])
    p.add_argument(
        "--preflight-validate-inputs",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Validate strict-summary/manifest/commercial external accuracy inputs before running steps.",
    )
    p.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--fail-fast", action=argparse.BooleanOptionalAction, default=True)
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    summary = run_batch(args)
    print(
        json.dumps(
            {
                "date_tag": summary["date_tag"],
                "mode": summary["mode"],
                "dry_run": summary["dry_run"],
                "pass": summary["pass"],
                "executed_steps": summary["executed_steps"],
                "total_steps": summary["total_steps"],
                "failed_step_index": summary["failed_step_index"],
                "summary_json": summary["paths"]["batch_summary_json"],
                "summary_md": summary["paths"]["batch_summary_md"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    if not bool(summary["pass"]):
        sys.exit(2)


if __name__ == "__main__":
    main()
