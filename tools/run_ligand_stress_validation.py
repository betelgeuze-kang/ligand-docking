#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import json
import math
import os
import signal
import statistics
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

try:
    from tools.update_closeout_latest import write_closeout as _write_closeout_latest
except Exception:  # pragma: no cover
    _write_closeout_latest = None


_STOP_REQUESTED = False

DEFAULT_GPCR_GUARDED_100K_READINESS_JSON = "runs/gpcr_guarded_100k_rerun_readiness_current.json"


def _signal_stop(_signum: int, _frame: object) -> None:
    global _STOP_REQUESTED
    _STOP_REQUESTED = True


def _acquire_instance_lock(lock_path: str) -> Dict[str, Any]:
    path = str(lock_path or "").strip()
    if not path:
        return {"ok": True, "enabled": False, "fd": None, "lock_path": "", "owner": ""}
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        owner = ""
        try:
            os.lseek(fd, 0, os.SEEK_SET)
            owner = os.read(fd, 256).decode("utf-8", errors="ignore").strip()
        except Exception:
            owner = ""
        try:
            os.close(fd)
        except Exception:
            pass
        return {"ok": False, "enabled": True, "fd": None, "lock_path": _abs_path(path), "owner": owner}
    os.ftruncate(fd, 0)
    os.lseek(fd, 0, os.SEEK_SET)
    os.write(fd, str(os.getpid()).encode("utf-8"))
    return {"ok": True, "enabled": True, "fd": fd, "lock_path": _abs_path(path), "owner": str(os.getpid())}


def _release_instance_lock(lock_meta: Dict[str, Any]) -> None:
    fd = lock_meta.get("fd") if isinstance(lock_meta, dict) else None
    if not isinstance(fd, int) or fd < 0:
        return
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    except Exception:
        pass
    try:
        os.close(fd)
    except Exception:
        pass


def _ensure_parent(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


def _abs_path(path: str) -> str:
    p = str(path or "").strip()
    if not p:
        return ""
    try:
        return os.path.abspath(os.path.expanduser(p))
    except Exception:
        return p


def _attach_artifacts_abs(payload: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(payload) if isinstance(payload, dict) else {}
    arts = out.get("artifacts", {})
    abs_map: Dict[str, str] = {}
    if isinstance(arts, dict):
        for k, v in arts.items():
            if isinstance(v, str) and str(v).strip():
                abs_map[str(k)] = _abs_path(str(v))
    if abs_map:
        out["artifacts_abs"] = abs_map
    return out


def _atomic_write_json(path: str, obj: Dict[str, Any]) -> None:
    _ensure_parent(path)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def _read_json(path: str) -> Dict[str, Any]:
    src = str(path).strip()
    if (not src) or (not os.path.exists(src)):
        return {}
    try:
        with open(src, "r", encoding="utf-8") as f:
            obj = json.load(f)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        # Keep stress orchestrator alive even if child summary is malformed/partial.
        return {}


def _can_resume_stage3_only(run_prefix: str) -> bool:
    prefix = str(run_prefix or "").strip()
    if not prefix:
        return False
    stage2_summary = _read_json(f"{prefix}_stage2_traj_summary.json")
    if not isinstance(stage2_summary, dict) or not stage2_summary:
        return False
    queue_rows = int(
        stage2_summary.get("queue_rows", stage2_summary.get("queue_rows_total", 0)) or 0
    )
    ok_rows = int(stage2_summary.get("ok_rows", 0) or 0)
    failed_rows = int(stage2_summary.get("failed_rows", 0) or 0)
    if queue_rows <= 0:
        return False
    # Stage3-only retry is safe only when trajectory generation has already closed out.
    if ok_rows < queue_rows:
        return False
    if failed_rows > 0:
        return False
    return True


def _run_key(pos_target: int, size: int, rep: int) -> str:
    return f"p{int(pos_target)}_n{int(size)}_r{int(rep)}"


def _parse_int_list(spec: str) -> List[int]:
    out: List[int] = []
    for tok in str(spec or "").split(","):
        s = tok.strip()
        if not s:
            continue
        try:
            v = int(float(s))
        except Exception:
            continue
        if v > 0:
            out.append(v)
    return sorted(set(out))


def _parse_targets(spec: str) -> List[str]:
    out: List[str] = []
    for tok in str(spec or "").split(","):
        s = str(tok).strip()
        if s:
            out.append(s)
    return out


def _boolish(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return None


def _guarded_100k_readiness_preflight(
    *,
    args: argparse.Namespace,
    prof: Dict[str, Any],
    sizes: List[int],
    target_list: List[str],
) -> Dict[str, Any]:
    cli_enforce = _boolish(getattr(args, "enforce_guarded_100k_readiness", None))
    profile_enforce = _boolish(prof.get("enforce_guarded_100k_readiness"))
    has_gpcr_target = any("GPCR" in str(target).upper() for target in target_list)
    has_100k_size = bool(sizes) and max(int(size) for size in sizes) >= 100000
    auto_enforce = has_gpcr_target and has_100k_size
    enforced = bool(cli_enforce if cli_enforce is not None else (profile_enforce if profile_enforce is not None else auto_enforce))
    readiness_json = str(
        getattr(args, "guarded_100k_readiness_json", "") or prof.get("guarded_100k_readiness_json", "")
        or DEFAULT_GPCR_GUARDED_100K_READINESS_JSON
    ).strip()
    payload = _read_json(readiness_json) if enforced else {}
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    claim_review_eligible = bool(
        summary.get("eligible") is True or str(summary.get("status", "")).lower() == "eligible"
    )
    launch_eligible = bool(
        summary.get("launch_eligible") is True or str(summary.get("launch_status", "")).lower() == "eligible"
    )
    eligible = bool(claim_review_eligible or launch_eligible)
    launch_blockers = summary.get("launch_blockers") if isinstance(summary.get("launch_blockers"), list) else []
    blockers = launch_blockers or (summary.get("blockers") if isinstance(summary.get("blockers"), list) else [])
    if enforced and not payload:
        blockers = ["guarded_100k_readiness_missing"]
    elif enforced and not eligible and not blockers:
        blockers = ["guarded_100k_readiness_not_eligible"]
    return {
        "enforced": bool(enforced),
        "ok": bool((not enforced) or eligible),
        "eligible": bool(eligible),
        "launch_eligible": bool(launch_eligible),
        "claim_review_eligible": bool(claim_review_eligible),
        "readiness_json": readiness_json,
        "blockers": blockers,
        "has_gpcr_target": bool(has_gpcr_target),
        "has_100k_size": bool(has_100k_size),
        "auto_enforce": bool(auto_enforce),
        "claim_promotion_allowed": False,
    }


def _probe_torch_gpu() -> Dict[str, Any]:
    try:
        import torch  # type: ignore

        available = bool(torch.cuda.is_available())
        count = int(torch.cuda.device_count()) if available else 0
        names: List[str] = []
        if count > 0:
            for idx in range(count):
                try:
                    names.append(str(torch.cuda.get_device_name(idx)))
                except Exception:
                    names.append(f"cuda:{idx}")
        return {
            "torch_import_ok": True,
            "torch_version": str(getattr(torch, "__version__", "")),
            "torch_cuda_available": available,
            "torch_cuda_device_count": count,
            "torch_cuda_device_names": names,
            "error": "",
        }
    except Exception as exc:
        return {
            "torch_import_ok": False,
            "torch_version": "",
            "torch_cuda_available": False,
            "torch_cuda_device_count": 0,
            "torch_cuda_device_names": [],
            "error": f"{type(exc).__name__}: {exc}",
        }


def _gpu_backend_preflight(*, prof: Dict[str, Any]) -> Dict[str, Any]:
    trajectory_mode = str(prof.get("trajectory_engine_mode", "")).strip().lower()
    require_rust_hip = bool(prof.get("require_rust_hip", False))
    abort_on_cpu_backend = bool(prof.get("traj_abort_on_cpu_backend", False))
    required = bool(require_rust_hip or trajectory_mode == "rust_hip" or abort_on_cpu_backend)
    probe = _probe_torch_gpu() if required else {}
    ok = bool(
        (not required)
        or (
            probe.get("torch_import_ok") is True
            and probe.get("torch_cuda_available") is True
            and int(probe.get("torch_cuda_device_count") or 0) > 0
        )
    )
    blockers: List[str] = []
    if required and not bool(probe.get("torch_import_ok", False)):
        blockers.append("torch_gpu_probe_failed")
    if required and not bool(probe.get("torch_cuda_available", False)):
        blockers.append("torch_cuda_unavailable")
    if required and int(probe.get("torch_cuda_device_count") or 0) <= 0:
        blockers.append("torch_cuda_device_count_zero")
    return {
        "checked": bool(required),
        "required": bool(required),
        "ok": bool(ok),
        "trajectory_engine_mode": trajectory_mode,
        "require_rust_hip": bool(require_rust_hip),
        "traj_abort_on_cpu_backend": bool(abort_on_cpu_backend),
        "blockers": sorted(set(blockers)),
        **probe,
        "next_required_step": (
            "Expose a ROCm/CUDA torch device before starting expensive hard-decoy or trajectory stages."
            if required and not ok
            else "GPU backend is visible for the rust_hip trajectory stage."
            if required
            else "GPU backend preflight not required for this profile."
        ),
    }


def _parse_roles(spec: str) -> List[str]:
    return [tok.strip() for tok in str(spec or "").split(",") if tok.strip()]


def _run(cmd: List[str], env: Dict[str, str]) -> Dict[str, Any]:
    p = subprocess.run(cmd, text=True, capture_output=True, env=env)
    return {
        "ok": bool(p.returncode == 0),
        "returncode": int(p.returncode),
        "cmd": cmd,
        "cmd_str": " ".join(cmd),
        "stdout_tail": "\n".join((p.stdout or "").splitlines()[-80:]),
        "stderr_tail": "\n".join((p.stderr or "").splitlines()[-80:]),
    }


def _profile_traj_prod_args(prof: Dict[str, Any]) -> List[str]:
    return [
        "--traj-prod-stage2-preset",
        str(prof.get("traj_prod_stage2_preset", "off")),
        "--traj-prod-stage2-preset-strict"
        if bool(prof.get("traj_prod_stage2_preset_strict", False))
        else "--no-traj-prod-stage2-preset-strict",
        "--traj-prod-speedpack"
        if bool(prof.get("traj_prod_speedpack", False))
        else "--no-traj-prod-speedpack",
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
        "--traj-prod-profile-intent",
        str(prof.get("traj_prod_profile_intent", "")),
        "--traj-prod-light-artifacts"
        if bool(prof.get("traj_prod_light_artifacts", True))
        else "--no-traj-prod-light-artifacts",
        "--traj-prod-light-progress-every-jobs",
        str(int(prof.get("traj_prod_light_progress_every_jobs", 250))),
    ]


def _profile_stage2_runtime_args(prof: Dict[str, Any]) -> List[str]:
    cli: List[str] = []
    if "traj_resume_existing" in prof:
        cli.append("--traj-resume-existing" if bool(prof.get("traj_resume_existing", True)) else "--no-traj-resume-existing")
    if "traj_job_batch_size" in prof:
        cli.extend(["--traj-job-batch-size", str(int(prof.get("traj_job_batch_size", 0)))])
    if str(prof.get("traj_job_batch_autotune_candidates", "")).strip():
        cli.extend(["--traj-job-batch-autotune-candidates", str(prof.get("traj_job_batch_autotune_candidates"))])
    if "traj_job_batch_autotune_frames" in prof:
        cli.extend(["--traj-job-batch-autotune-frames", str(int(prof.get("traj_job_batch_autotune_frames", 12)))])
    if "traj_engine_cache_max_entries" in prof:
        cli.extend(["--traj-engine-cache-max-entries", str(int(prof.get("traj_engine_cache_max_entries", 16)))])
    if "traj_writer_max_pending" in prof:
        cli.extend(["--traj-writer-max-pending", str(int(prof.get("traj_writer_max_pending", 64)))])
    return cli


def _profile_residual_prototype_args(prof: Dict[str, Any]) -> List[str]:
    cli: List[str] = [
        "--stage3-residual-prototype-enabled"
        if bool(prof.get("residual_prototype_enabled", False))
        else "--no-stage3-residual-prototype-enabled",
        "--stage3-residual-prototype-mode",
        str(prof.get("residual_prototype_mode", "shadow_only")),
        "--stage3-residual-prototype-family",
        str(prof.get("residual_prototype_family", "")),
        "--stage3-residual-prototype-runtime-hook-ready"
        if bool(prof.get("residual_prototype_runtime_hook_ready", False))
        else "--no-stage3-residual-prototype-runtime-hook-ready",
    ]
    spec_json = str(prof.get("residual_prototype_spec_json", "") or "").strip()
    if spec_json:
        cli.extend(["--stage3-residual-prototype-spec-json", spec_json])
    if prof.get("residual_prototype_max_abs_delta_score", None) not in (None, ""):
        cli.extend(
            [
                "--stage3-residual-prototype-max-abs-delta-score",
                str(float(prof.get("residual_prototype_max_abs_delta_score"))),
            ]
        )
    if prof.get("residual_prototype_yellow_band_abs_delta_score", None) not in (None, ""):
        cli.extend(
            [
                "--stage3-residual-prototype-yellow-band-abs-delta-score",
                str(float(prof.get("residual_prototype_yellow_band_abs_delta_score"))),
            ]
        )
    return cli


def _profile_score_reference_args(prof: Dict[str, Any]) -> List[str]:
    mode = str(prof.get("score_reference_scaling_mode", "run_local") or "run_local").strip()
    stats_json = str(prof.get("score_reference_stats_json", "") or "").strip()
    cli = ["--stage3-score-reference-scaling-mode", mode]
    if stats_json:
        cli.extend(["--stage3-score-reference-stats-json", stats_json])
    return cli


def _profile_traj_prod_summary(prof: Dict[str, Any]) -> Dict[str, Any]:
    requested = str(prof.get("traj_prod_stage2_preset", "off") or "off")
    speedpack = bool(prof.get("traj_prod_speedpack", False))
    early_stop = bool(prof.get("traj_prod_early_stop_enabled", False))
    light_artifacts = bool(prof.get("traj_prod_light_artifacts", True))
    profile_intent = str(prof.get("traj_prod_profile_intent", "") or "").strip()
    enabled = bool(requested != "off" or speedpack or early_stop)
    warnings: List[str] = []
    if enabled and (not profile_intent):
        warnings.append("traj_prod knobs are enabled without traj_prod_profile_intent; stress-level auditability is reduced.")
    return {
        "enabled": bool(enabled),
        "profile_intent": profile_intent,
        "requested_preset": requested,
        "strict": bool(prof.get("traj_prod_stage2_preset_strict", False)),
        "speedpack": bool(speedpack),
        "adaptive_frame_budget": bool(prof.get("traj_prod_adaptive_frame_budget", True)),
        "early_stop": bool(early_stop),
        "light_artifacts": bool(light_artifacts),
        "light_progress_every_jobs": int(prof.get("traj_prod_light_progress_every_jobs", 250)),
        "warnings": warnings,
    }


def _extract_traj_prod_audit_fields(summary_payload: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(summary_payload) if isinstance(summary_payload, dict) else {}
    top_level = payload.get("traj_prod", {}) if isinstance(payload.get("traj_prod"), dict) else {}
    sla_payload = ((payload.get("stages") or {}).get("stage8_sla") or {})
    if not isinstance(sla_payload, dict):
        sla_payload = {}
    op = sla_payload.get("traj_prod_operational_summary", {})
    if not isinstance(op, dict):
        op = {}
    stage2_engine = sla_payload.get("traj_stage2_engine_summary", {})
    if not isinstance(stage2_engine, dict):
        stage2_engine = {}
    warnings = [str(x) for x in op.get("warnings", top_level.get("warnings", [])) if str(x).strip()]
    return {
        "traj_prod_enabled": bool(op.get("enabled", top_level.get("enabled", False))),
        "traj_prod_profile_intent": str(op.get("profile_intent", top_level.get("profile_intent", "")) or "").strip(),
        "traj_prod_requested_preset": str(op.get("requested_preset", top_level.get("requested_preset", "off")) or "off"),
        "traj_prod_resolved_preset": str(op.get("resolved_preset", top_level.get("resolved_preset", "off")) or "off"),
        "traj_prod_strict_enabled": bool(op.get("strict_enabled", top_level.get("strict", False))),
        "traj_prod_strict_status": str(op.get("strict_status", "") or ""),
        "traj_prod_strict_error": str(op.get("strict_error", "") or ""),
        "traj_prod_warning_count": int(op.get("warning_count", len(warnings)) or 0),
        "traj_prod_warnings": warnings,
        "traj_prod_speedpack": bool(op.get("speedpack", top_level.get("speedpack", False))),
        "traj_prod_adaptive_frame_budget": bool(op.get("adaptive_frame_budget", top_level.get("adaptive_frame_budget", False))),
        "traj_prod_early_stop": bool(op.get("early_stop", top_level.get("early_stop", False))),
        "traj_prod_light_artifacts": bool(op.get("light_artifacts", top_level.get("light_artifacts", False))),
        "traj_prod_light_progress_every_jobs": int(op.get("light_progress_every_jobs", top_level.get("light_progress_every_jobs", 250)) or 250),
        "traj_prod_hinted_families": [str(x) for x in op.get("hinted_families", top_level.get("hinted_families", [])) if str(x).strip()],
        "traj_prod_effective_traj_frames": _safe_num(op.get("effective_traj_frames")),
        "traj_prod_effective_batch_autotune_candidates": str(op.get("effective_batch_autotune_candidates", "") or ""),
        "traj_prod_effective_writer_workers": _safe_num(op.get("effective_writer_workers")),
        "traj_prod_effective_writer_max_pending": _safe_num(op.get("effective_writer_max_pending")),
        "traj_prod_effective_dynamic_adress_fraction": _safe_num(op.get("effective_dynamic_adress_fraction")),
        "traj_prod_effective_dynamic_adress_max_protein_residues": _safe_num(op.get("effective_dynamic_adress_max_protein_residues")),
        "traj_prod_effective_frame_budget_tiers": str(op.get("effective_frame_budget_tiers", "") or ""),
        "traj_prod_effective_min_frames": _safe_num(op.get("effective_min_frames")),
        "traj_prod_effective_early_stop_min_frames": _safe_num(op.get("effective_early_stop_min_frames")),
        "traj_prod_effective_early_stop_window": _safe_num(op.get("effective_early_stop_window")),
        "traj_prod_effective_early_stop_contact_drift": _safe_num(op.get("effective_early_stop_contact_drift")),
        "traj_prod_effective_early_stop_min_distance_drift_A": _safe_num(op.get("effective_early_stop_min_distance_drift_A")),
        "traj_prod_effective_early_stop_max_mean_min_distance_A": _safe_num(op.get("effective_early_stop_max_mean_min_distance_A")),
        "traj_stage2_engine_prod_mode": bool(stage2_engine.get("prod_mode", False)),
        "traj_stage2_engine_prod_light_artifacts": bool(stage2_engine.get("prod_light_artifacts", False)),
        "traj_stage2_engine_prod_frame_budget_applied_count": _safe_num(stage2_engine.get("prod_frame_budget_applied_count")),
        "traj_stage2_engine_prod_early_stop_batch_count": _safe_num(stage2_engine.get("prod_early_stop_batch_count")),
        "traj_stage2_engine_prod_early_stop_row_count": _safe_num(stage2_engine.get("prod_early_stop_row_count")),
        "traj_stage2_engine_mean_sim_frames_count": _safe_num(stage2_engine.get("mean_sim_frames_count")),
        "traj_stage2_engine_mean_frames_effective_cap": _safe_num(stage2_engine.get("mean_frames_effective_cap")),
        "traj_stage2_engine_job_batch_derate_count": _safe_num(stage2_engine.get("job_batch_derate_count")),
        "traj_stage2_engine_target_tail_csv_present": bool(stage2_engine.get("target_tail_csv_present", False)),
        "traj_stage2_engine_manifest_chunks_dir_present": bool(stage2_engine.get("manifest_chunks_dir_present", False)),
        "traj_stage2_engine_summary_md_present": bool(stage2_engine.get("summary_md_present", False)),
    }


def _summarize_traj_prod_observability(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    row_list = [dict(row) for row in rows if isinstance(row, dict)]
    if not row_list:
        return {
            "completed_runs": 0,
            "enabled_runs": 0,
            "warning_runs": 0,
            "strict_error_runs": 0,
            "profile_intents": [],
            "requested_presets": [],
            "resolved_presets": [],
            "strict_statuses": [],
            "hinted_families": [],
            "effective_writer_workers": [],
            "effective_writer_max_pending": [],
            "effective_frame_budget_tiers": [],
            "effective_min_frames": [],
            "effective_early_stop_min_frames": [],
            "effective_early_stop_window": [],
        }

    def _sorted_unique(key: str) -> List[Any]:
        vals = []
        for row in row_list:
            val = row.get(key)
            if isinstance(val, list):
                vals.extend(val)
            elif val not in (None, ""):
                vals.append(val)
        return sorted(set(vals))

    return {
        "completed_runs": int(len(row_list)),
        "enabled_runs": int(sum(1 for row in row_list if bool(row.get("traj_prod_enabled", False)))),
        "warning_runs": int(sum(1 for row in row_list if int(row.get("traj_prod_warning_count", 0) or 0) > 0)),
        "strict_error_runs": int(sum(1 for row in row_list if str(row.get("traj_prod_strict_status", "") or "") == "error")),
        "profile_intents": [str(x) for x in _sorted_unique("traj_prod_profile_intent")],
        "requested_presets": [str(x) for x in _sorted_unique("traj_prod_requested_preset")],
        "resolved_presets": [str(x) for x in _sorted_unique("traj_prod_resolved_preset")],
        "strict_statuses": [str(x) for x in _sorted_unique("traj_prod_strict_status")],
        "hinted_families": [str(x) for x in _sorted_unique("traj_prod_hinted_families")],
        "effective_writer_workers": _sorted_unique("traj_prod_effective_writer_workers"),
        "effective_writer_max_pending": _sorted_unique("traj_prod_effective_writer_max_pending"),
        "effective_frame_budget_tiers": [str(x) for x in _sorted_unique("traj_prod_effective_frame_budget_tiers")],
        "effective_min_frames": _sorted_unique("traj_prod_effective_min_frames"),
        "effective_early_stop_min_frames": _sorted_unique("traj_prod_effective_early_stop_min_frames"),
        "effective_early_stop_window": _sorted_unique("traj_prod_effective_early_stop_window"),
        "engine_prod_mode_runs": int(sum(1 for row in row_list if bool(row.get("traj_stage2_engine_prod_mode", False)))),
        "engine_light_artifact_runs": int(sum(1 for row in row_list if bool(row.get("traj_stage2_engine_prod_light_artifacts", False)))),
        "engine_frame_budget_applied_counts": _sorted_unique("traj_stage2_engine_prod_frame_budget_applied_count"),
        "engine_early_stop_batch_counts": _sorted_unique("traj_stage2_engine_prod_early_stop_batch_count"),
        "engine_early_stop_row_counts": _sorted_unique("traj_stage2_engine_prod_early_stop_row_count"),
        "engine_mean_sim_frames_counts": _sorted_unique("traj_stage2_engine_mean_sim_frames_count"),
        "engine_mean_frames_effective_caps": _sorted_unique("traj_stage2_engine_mean_frames_effective_cap"),
        "engine_job_batch_derate_counts": _sorted_unique("traj_stage2_engine_job_batch_derate_count"),
        "engine_target_tail_csv_present_flags": _sorted_unique("traj_stage2_engine_target_tail_csv_present"),
        "engine_manifest_chunks_dir_present_flags": _sorted_unique("traj_stage2_engine_manifest_chunks_dir_present"),
        "engine_summary_md_present_flags": _sorted_unique("traj_stage2_engine_summary_md_present"),
    }


def _traj_prod_markdown_lines(
    requested_profile: Dict[str, Any],
    observed_summary: Dict[str, Any],
) -> List[str]:
    prof = dict(requested_profile) if isinstance(requested_profile, dict) else {}
    observed = dict(observed_summary) if isinstance(observed_summary, dict) else {}
    return [
        "## Production Stage2 Audit",
        "",
        f"- traj_prod_enabled: {prof.get('enabled')}",
        f"- traj_prod_profile_intent: `{str(prof.get('profile_intent', '') or '')}`",
        f"- traj_prod_requested_preset: `{str(prof.get('requested_preset', '') or '')}`",
        f"- traj_prod_strict_enabled: {prof.get('strict')}",
        f"- traj_prod_speedpack: {prof.get('speedpack')}",
        f"- traj_prod_adaptive_frame_budget: {prof.get('adaptive_frame_budget')}",
        f"- traj_prod_early_stop: {prof.get('early_stop')}",
        f"- traj_prod_light_artifacts: {prof.get('light_artifacts')}",
        f"- traj_prod_light_progress_every_jobs: {prof.get('light_progress_every_jobs')}",
        f"- traj_prod_requested_warnings: `{prof.get('warnings', [])}`",
        "",
        "### Observed Runtime",
        "",
        f"- completed_runs_with_traj_prod_metadata: {observed.get('completed_runs')}",
        f"- observed_enabled_runs: {observed.get('enabled_runs')}",
        f"- observed_warning_runs: {observed.get('warning_runs')}",
        f"- observed_strict_error_runs: {observed.get('strict_error_runs')}",
        f"- observed_profile_intents: `{observed.get('profile_intents', [])}`",
        f"- observed_requested_presets: `{observed.get('requested_presets', [])}`",
        f"- observed_resolved_presets: `{observed.get('resolved_presets', [])}`",
        f"- observed_strict_statuses: `{observed.get('strict_statuses', [])}`",
        f"- observed_hinted_families: `{observed.get('hinted_families', [])}`",
        f"- observed_effective_writer_workers: `{observed.get('effective_writer_workers', [])}`",
        f"- observed_effective_writer_max_pending: `{observed.get('effective_writer_max_pending', [])}`",
        f"- observed_effective_frame_budget_tiers: `{observed.get('effective_frame_budget_tiers', [])}`",
        f"- observed_effective_min_frames: `{observed.get('effective_min_frames', [])}`",
        f"- observed_effective_early_stop_min_frames: `{observed.get('effective_early_stop_min_frames', [])}`",
        f"- observed_effective_early_stop_window: `{observed.get('effective_early_stop_window', [])}`",
        f"- observed_engine_prod_mode_runs: {observed.get('engine_prod_mode_runs')}",
        f"- observed_engine_light_artifact_runs: {observed.get('engine_light_artifact_runs')}",
        f"- observed_engine_frame_budget_applied_counts: `{observed.get('engine_frame_budget_applied_counts', [])}`",
        f"- observed_engine_early_stop_batch_counts: `{observed.get('engine_early_stop_batch_counts', [])}`",
        f"- observed_engine_early_stop_row_counts: `{observed.get('engine_early_stop_row_counts', [])}`",
        f"- observed_engine_mean_sim_frames_counts: `{observed.get('engine_mean_sim_frames_counts', [])}`",
        f"- observed_engine_mean_frames_effective_caps: `{observed.get('engine_mean_frames_effective_caps', [])}`",
        f"- observed_engine_job_batch_derate_counts: `{observed.get('engine_job_batch_derate_counts', [])}`",
        f"- observed_engine_target_tail_csv_present_flags: `{observed.get('engine_target_tail_csv_present_flags', [])}`",
        f"- observed_engine_manifest_chunks_dir_present_flags: `{observed.get('engine_manifest_chunks_dir_present_flags', [])}`",
        f"- observed_engine_summary_md_present_flags: `{observed.get('engine_summary_md_present_flags', [])}`",
    ]


def _safe_num(v: Any) -> Optional[float]:
    if isinstance(v, (int, float)):
        return float(v)
    return None


def _rebalance_ligand_csv_by_role(
    labels_csv: str,
    split_csv: str,
    out_csv: str,
    role_order: Optional[List[str]] = None,
) -> str:
    labels = pd.read_csv(labels_csv)
    split = pd.read_csv(split_csv)
    req = {"target", "ligand_id", "role"}
    if labels.empty or split.empty or any(c not in labels.columns for c in ("target", "ligand_id")) or any(c not in split.columns for c in req):
        labels.to_csv(out_csv, index=False)
        return out_csv

    merged = labels.merge(
        split[["target", "ligand_id", "role"]],
        on=["target", "ligand_id"],
        how="left",
    )
    merged["role"] = merged["role"].fillna("")
    merged["_ord"] = list(range(len(merged)))

    base_order = role_order or ["fit", "far_ood_eval", "id_eval", "near_ood_eval", "eval", "ood_eval", ""]
    seen = set()
    all_roles = [str(r) for r in merged["role"].dropna().astype(str).unique().tolist()]
    final_roles: List[str] = []
    for r in base_order + all_roles:
        if r in seen:
            continue
        seen.add(r)
        final_roles.append(r)

    buckets: Dict[str, pd.DataFrame] = {}
    for r in final_roles:
        buckets[r] = merged[merged["role"] == r].sort_values("_ord")

    ptr = {r: 0 for r in final_roles}
    out_rows: List[pd.Series] = []
    total = int(len(merged))
    while len(out_rows) < total:
        advanced = False
        for r in final_roles:
            df = buckets[r]
            i = ptr[r]
            if i < len(df):
                out_rows.append(df.iloc[i])
                ptr[r] = i + 1
                advanced = True
        if not advanced:
            break

    if len(out_rows) <= 0:
        merged.drop(columns=["_ord"], errors="ignore").to_csv(out_csv, index=False)
        return out_csv

    out_df = pd.DataFrame(out_rows).drop(columns=["_ord"], errors="ignore")
    out_df.to_csv(out_csv, index=False)
    return out_csv


def _augment_eval_positive_count(
    labels_csv: str,
    split_csv: str,
    out_labels_csv: str,
    out_split_csv: str,
    *,
    min_positive_count: int,
    eval_roles: List[str],
) -> Dict[str, Any]:
    labels = pd.read_csv(labels_csv)
    split = pd.read_csv(split_csv)
    required_labels = {"target", "ligand_id", "is_binder"}
    required_split = {"target", "ligand_id", "role"}
    if any(c not in labels.columns for c in required_labels):
        raise ValueError(f"labels csv missing required columns: {sorted(required_labels)}")
    if any(c not in split.columns for c in required_split):
        raise ValueError(f"split csv missing required columns: {sorted(required_split)}")

    if labels.empty or split.empty or int(max(min_positive_count, 0)) <= 0:
        labels.to_csv(out_labels_csv, index=False)
        split.to_csv(out_split_csv, index=False)
        return {
            "applied": False,
            "min_positive_count": int(max(min_positive_count, 0)),
            "positive_count_before": 0,
            "positive_count_after": 0,
            "added_rows": 0,
            "reason": "no_augmentation_needed",
        }

    roles = list(eval_roles) if eval_roles else ["far_ood_eval", "ood_eval", "eval", "near_ood_eval", "id_eval"]
    labels_base = labels.copy()
    # labels csv may already include role from prior balancing; normalize to split role source.
    if "role" in labels_base.columns:
        labels_base = labels_base.drop(columns=["role"], errors="ignore")
    merged = labels_base.merge(split[["target", "ligand_id", "role"]], on=["target", "ligand_id"], how="left")
    if "role" not in merged.columns:
        for alt in ("role_y", "role_x"):
            if alt in merged.columns:
                merged["role"] = merged[alt]
                break
    if "role" not in merged.columns:
        raise ValueError("split merge failed to provide role column")
    eval_df = merged[merged["role"].astype(str).isin(roles)].copy()
    pos_eval = eval_df[eval_df["is_binder"].astype(int) == 1].copy()
    before = int(len(pos_eval))
    if before >= int(min_positive_count):
        labels.to_csv(out_labels_csv, index=False)
        split.to_csv(out_split_csv, index=False)
        return {
            "applied": False,
            "min_positive_count": int(min_positive_count),
            "positive_count_before": int(before),
            "positive_count_after": int(before),
            "added_rows": 0,
            "reason": "already_satisfied",
        }

    if pos_eval.empty:
        raise ValueError("cannot augment positive count: no positive rows in eval roles")

    existing_keys = set(labels["target"].astype(str) + "::" + labels["ligand_id"].astype(str))
    added_labels: List[Dict[str, Any]] = []
    added_splits: List[Dict[str, Any]] = []
    needed = int(min_positive_count - before)
    pos_rows = pos_eval.reset_index(drop=True)
    pos_n = int(len(pos_rows))

    for i in range(needed):
        src = pos_rows.iloc[int(i % pos_n)].to_dict()
        target = str(src.get("target", ""))
        ligand_id = str(src.get("ligand_id", ""))
        src_role = str(src.get("role", roles[0] if roles else "eval"))
        # Distribute augmented positives across eval roles to avoid single-role concentration.
        role = str(roles[i % len(roles)]) if roles else src_role
        if not target or not ligand_id:
            continue
        base = f"{ligand_id}_posaug_{i + 1:05d}"
        candidate = base
        suffix = 1
        while f"{target}::{candidate}" in existing_keys:
            candidate = f"{base}_{suffix}"
            suffix += 1
        existing_keys.add(f"{target}::{candidate}")

        row = dict(src)
        row["ligand_id"] = candidate
        row["is_binder"] = 1
        row["source"] = f"{row.get('source', 'synthetic_positive')}::posaug"
        # Keep deterministic mild perturbation for calibration stability.
        if "reference_binding_kcal_mol" in row:
            try:
                base_e = float(row["reference_binding_kcal_mol"])
                jitter = float(((i % 7) - 3) * 0.03)
                row["reference_binding_kcal_mol"] = float(base_e + jitter)
            except Exception:
                pass
        row.pop("role", None)
        added_labels.append(row)
        added_splits.append({"target": target, "ligand_id": candidate, "role": role})

    labels_out = pd.concat([labels, pd.DataFrame(added_labels)], ignore_index=True)
    split_out = pd.concat([split, pd.DataFrame(added_splits)], ignore_index=True)
    labels_out.to_csv(out_labels_csv, index=False)
    split_out.to_csv(out_split_csv, index=False)

    after = before + int(len(added_labels))
    return {
        "applied": bool(len(added_labels) > 0),
        "min_positive_count": int(min_positive_count),
        "positive_count_before": int(before),
        "positive_count_after": int(after),
        "added_rows": int(len(added_labels)),
        "roles": roles,
        "out_labels_csv": str(out_labels_csv),
        "out_split_csv": str(out_split_csv),
    }


def run_stress(args: argparse.Namespace) -> Dict[str, Any]:
    profile_json = str(args.profile_json).strip()
    if (not profile_json) or (not os.path.exists(profile_json)):
        raise FileNotFoundError(f"profile json not found: {profile_json}")
    prof = _read_json(profile_json)

    sizes = _parse_int_list(str(args.ligand_sizes))
    if not sizes:
        raise ValueError("no valid ligand sizes")
    repeats = int(max(args.repeats, 1))

    date_tag = str(args.date_tag).strip() or dt.date.today().isoformat()
    out_prefix = str(args.out_prefix).strip() or f"runs/ligand_stress_validation_{date_tag}"
    _ensure_parent(f"{out_prefix}_summary.json")
    state_json = str(args.state_json).strip() or f"{out_prefix}_state.json"
    lock_meta = {
        "enabled": bool(getattr(args, "single_instance", True)),
        "ok": True,
        "lock_path": "",
        "owner": "",
        "fd": None,
    }
    if bool(lock_meta["enabled"]):
        lock_path = str(getattr(args, "lock_file", "")).strip() or f"{out_prefix}.lock"
        lock_meta = _acquire_instance_lock(lock_path)
        if not bool(lock_meta.get("ok", False)):
            payload = {
                "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
                "pass": False,
                "stopped": False,
                "failed_stage": "stage_lock",
                "profile_json": profile_json,
                "runs": [],
                "aggregate": [],
                "failures": [],
                "stages": {"stage_lock": {k: v for k, v in lock_meta.items() if k != "fd"}},
                "artifacts": {
                    "summary_json": f"{out_prefix}_summary.json",
                    "summary_md": f"{out_prefix}_summary.md",
                    "state_json": state_json,
                },
            }
            payload = _attach_artifacts_abs(payload)
            with open(f"{out_prefix}_summary.json", "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            return payload

    base_targets = str(args.targets).strip() or str(prof.get("targets", "KRAS_G12D,EGFR_KINASE,HIV1_PROTEASE"))
    target_list = _parse_targets(base_targets)
    target_count = max(1, len(target_list))
    guarded_100k_preflight = _guarded_100k_readiness_preflight(
        args=args,
        prof=prof,
        sizes=sizes,
        target_list=target_list,
    )
    if not bool(guarded_100k_preflight.get("ok", False)):
        payload = {
            "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
            "pass": False,
            "stopped": False,
            "failed_stage": "guarded_100k_readiness_preflight",
            "profile_json": profile_json,
            "runs": [],
            "aggregate": [],
            "failures": [],
            "stages": {"guarded_100k_readiness_preflight": guarded_100k_preflight},
            "artifacts": {
                "summary_json": f"{out_prefix}_summary.json",
                "summary_md": f"{out_prefix}_summary.md",
                "state_json": state_json,
            },
        }
        payload = _attach_artifacts_abs(payload)
        with open(f"{out_prefix}_summary.json", "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        with open(f"{out_prefix}_summary.md", "w", encoding="utf-8") as f:
            f.write(
                "\n".join(
                    [
                        "# Ligand Stress Validation",
                        "",
                        f"- pass: {payload['pass']}",
                        f"- failed_stage: `{payload['failed_stage']}`",
                        f"- guarded_100k_readiness_json: `{guarded_100k_preflight.get('readiness_json', '')}`",
                        f"- blockers: {guarded_100k_preflight.get('blockers', [])}",
                    ]
                )
                + "\n"
            )
        _release_instance_lock(lock_meta)
        return payload

    gpu_backend_preflight = _gpu_backend_preflight(prof=prof)
    if not bool(gpu_backend_preflight.get("ok", False)):
        payload = {
            "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
            "pass": False,
            "stopped": False,
            "failed_stage": "gpu_backend_preflight",
            "profile_json": profile_json,
            "runs": [],
            "aggregate": [],
            "failures": [],
            "stages": {"gpu_backend_preflight": gpu_backend_preflight},
            "artifacts": {
                "summary_json": f"{out_prefix}_summary.json",
                "summary_md": f"{out_prefix}_summary.md",
                "state_json": state_json,
            },
        }
        payload = _attach_artifacts_abs(payload)
        with open(f"{out_prefix}_summary.json", "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        with open(f"{out_prefix}_summary.md", "w", encoding="utf-8") as f:
            f.write(
                "\n".join(
                    [
                        "# Ligand Stress Validation",
                        "",
                        f"- pass: {payload['pass']}",
                        f"- failed_stage: `{payload['failed_stage']}`",
                        f"- trajectory_engine_mode: `{gpu_backend_preflight.get('trajectory_engine_mode', '')}`",
                        f"- torch_cuda_available: `{gpu_backend_preflight.get('torch_cuda_available', False)}`",
                        f"- torch_cuda_device_count: `{gpu_backend_preflight.get('torch_cuda_device_count', 0)}`",
                        f"- blockers: {gpu_backend_preflight.get('blockers', [])}",
                    ]
                )
                + "\n"
            )
        _release_instance_lock(lock_meta)
        return payload

    gate = prof.get("gate", {}) if isinstance(prof.get("gate"), dict) else {}
    strict_gate = prof.get("strict_gate", {}) if isinstance(prof.get("strict_gate"), dict) else {}
    smoke = prof.get("smoke", {}) if isinstance(prof.get("smoke"), dict) else {}
    full = prof.get("full", {}) if isinstance(prof.get("full"), dict) else {}
    retry_cfg = prof.get("retry", {}) if isinstance(prof.get("retry"), dict) else {}

    env = dict(os.environ)
    env["FORCE_RUST_HIP"] = "1"
    env["RUST_HIP_USE_GPU_NBLIST_BUILDER"] = "1"
    env["AI_ROUTER_ONNX_ALLOW_CPU"] = "0"
    env["MD_GPU_ONLY"] = "1"

    calib_ref_csv = str(prof.get("calibration_reference_csv", "config/ligand_binding_reference_expanded_v2.csv"))
    ranking_labels_csv = str(prof.get("ranking_labels_csv", "config/ligand_binding_reference_expanded_v2.csv"))
    eval_split_csv = str(prof.get("eval_split_csv", ""))
    ligand_csv = str(prof.get("ligand_csv", "config/ligand_smoke_seed_v1.csv"))
    positive_sweep = _parse_int_list(str(args.positive_count_sweep).strip() or str(prof.get("positive_count_sweep", "")))
    positive_targets = sorted(set(positive_sweep)) if positive_sweep else [0]
    auto_augment_positive = bool(args.auto_augment_positive_count) or bool(prof.get("positive_counter_auto_augment", False))
    positive_eval_roles = _parse_roles(str(prof.get("positive_counter_eval_roles", prof.get("ranking_eval_roles", "eval"))))
    heavy_artifacts_root = str(args.heavy_artifacts_root).strip() or str(prof.get("heavy_artifacts_root", "")).strip()
    auto_heavy_artifacts_root = (
        bool(prof.get("auto_heavy_artifacts_root", True))
        if (args.auto_heavy_artifacts_root is None)
        else bool(args.auto_heavy_artifacts_root)
    )
    data_contract_json = str(args.data_contract_json).strip() or str(
        prof.get("data_contract_json", "config/ligand_data_contract_v1.json")
    ).strip()
    enforce_data_contract = (
        bool(prof.get("enforce_data_contract", True))
        if (args.enforce_data_contract is None)
        else bool(args.enforce_data_contract)
    )
    max_attempts_per_run = int(args.max_attempts_per_run) if int(args.max_attempts_per_run) > 0 else int(max(1, int(retry_cfg.get("max_attempts", 1))))
    retry_sleep_sec = float(args.retry_sleep_sec) if float(args.retry_sleep_sec) >= 0.0 else float(max(0.0, float(retry_cfg.get("sleep_sec", 5.0))))
    retry_backoff = float(args.retry_backoff) if float(args.retry_backoff) > 0.0 else float(max(1.0, float(retry_cfg.get("backoff", 1.0))))
    retry_backoff = float(max(1.0, retry_backoff))
    resume_retry_failed_runs = bool(args.resume_retry_failed_runs)
    resume_stage3_only_on_retry = bool(prof.get("resume_stage3_only_on_retry", True))
    gate_enforcement_mode = str(prof.get("gate_enforcement_mode", "operational")).strip().lower()
    if gate_enforcement_mode not in {"operational", "strict", "both"}:
        gate_enforcement_mode = "operational"

    planned_keys: List[str] = []
    fail_fast_triggered = False
    for pos_target in positive_targets:
        for size in sizes:
            for rep in range(1, repeats + 1):
                planned_keys.append(_run_key(int(pos_target), int(size), int(rep)))

    state: Dict[str, Any] = {}
    if bool(args.resume) and os.path.exists(state_json):
        state = _read_json(state_json)
    if not isinstance(state, dict):
        state = {}
    if (state.get("out_prefix") != out_prefix) or (state.get("profile_json") != profile_json):
        state = {}

    started_at = str(state.get("started_at", "") or dt.datetime.now().isoformat(timespec="seconds"))
    completed_keys = {
        str(x).strip()
        for x in (state.get("completed_keys") or [])
        if str(x).strip()
    }
    row_store = state.get("row_store", {})
    if not isinstance(row_store, dict):
        row_store = {}
    fail_store = state.get("fail_store", {})
    if not isinstance(fail_store, dict):
        fail_store = {}
    pre_stage_state = state.get("pre_stage_state", {})
    if not isinstance(pre_stage_state, dict):
        pre_stage_state = {}
    attempt_store = state.get("attempt_store", {})
    if not isinstance(attempt_store, dict):
        attempt_store = {}

    def _save_state(current: Optional[Dict[str, Any]] = None, stopped: bool = False) -> None:
        snap = {
            "version": 1,
            "updated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
            "started_at": started_at,
            "out_prefix": out_prefix,
            "profile_json": profile_json,
            "date_tag": date_tag,
            "ligand_sizes": [int(x) for x in sizes],
            "repeats": int(repeats),
            "positive_count_targets": [int(x) for x in positive_targets],
            "planned_keys": list(planned_keys),
            "completed_keys": sorted(completed_keys),
            "row_store": row_store,
            "fail_store": fail_store,
            "pre_stage_state": pre_stage_state,
            "attempt_store": attempt_store,
            "current": current or {},
            "stopped": bool(stopped),
            "resume_enabled": bool(args.resume),
            "resume_retry_failed_runs": bool(resume_retry_failed_runs),
            "max_attempts_per_run": int(max_attempts_per_run),
            "retry_sleep_sec": float(retry_sleep_sec),
            "retry_backoff": float(retry_backoff),
        }
        _atomic_write_json(state_json, snap)

    _save_state(current={"status": "initialized"})

    pre_stage: Dict[str, Any] = {"ok": True, "skipped": True, "cmd": [], "cmd_str": ""}
    if bool(prof.get("build_hard_decoy_benchmark", False)):
        hard_labels = f"{out_prefix}_hard_decoy_labels.csv"
        hard_split = f"{out_prefix}_hard_decoy_split.csv"
        hard_progress = f"{out_prefix}_hard_decoy_progress.json"
        hard_labels_balanced = f"{out_prefix}_hard_decoy_labels_balanced.csv"
        hard_summary_json = f"{out_prefix}_hard_decoy_summary.json"
        hard_summary_obj = _read_json(hard_summary_json) if os.path.exists(hard_summary_json) else {}
        can_reuse_pre = bool(args.resume) and all(
            os.path.exists(p)
            for p in [hard_labels, hard_split, hard_summary_json]
        ) and (
            bool(pre_stage_state.get("done", False))
            or bool(hard_summary_obj.get("pass", False))
        )
        if can_reuse_pre:
            pre_stage = {"ok": True, "skipped": True, "reused": True, "cmd": [], "cmd_str": ""}
        else:
            if os.path.exists(hard_progress):
                try:
                    os.remove(hard_progress)
                except Exception:
                    pass
            pre_cmd = [
                sys.executable,
                "tools/build_hard_decoy_benchmark.py",
                "--reference-csv",
                str(prof.get("hard_decoy_reference_csv", ranking_labels_csv)),
                "--targets",
                str(prof.get("hard_decoy_targets", base_targets)),
                "--ligand-meta-csv",
                str(prof.get("hard_decoy_ligand_meta_csv", "")),
                "--target-meta-csv",
                str(prof.get("hard_decoy_target_meta_csv", "")),
                "--fit-targets",
                str(prof.get("hard_decoy_fit_targets", "")),
                "--ensure-roles",
                str(
                    prof.get(
                        "hard_decoy_ensure_roles",
                        "fit,id_eval,near_ood_eval,eval,far_ood_eval,ood_eval",
                    )
                ),
                "--min-rows-per-role",
                str(int(prof.get("hard_decoy_min_rows_per_role", 0))),
                "--rebalance-donor-roles",
                str(
                    prof.get(
                        "hard_decoy_rebalance_donor_roles",
                        "id_eval,near_ood_eval,eval,far_ood_eval,ood_eval",
                    )
                ),
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
                "--synth-generation-mode",
                str(prof.get("hard_decoy_synth_generation_mode", "random")),
                "--synth-global-unique"
                if bool(prof.get("hard_decoy_synth_global_unique", True))
                else "--no-synth-global-unique",
                "--synth-max-attempt-mult",
                str(int(prof.get("hard_decoy_synth_max_attempt_mult", 400))),
                "--synth-relax-3d"
                if bool(prof.get("hard_decoy_synth_relax_3d", True))
                else "--no-synth-relax-3d",
                "--synth-relax-max-iters",
                str(int(prof.get("hard_decoy_synth_relax_max_iters", 200))),
                "--synth-relax-cache-json",
                str(prof.get("hard_decoy_synth_relax_cache_json", "runs/hard_decoy_relax_cache.json")),
                "--progress-every-attempts",
                str(int(prof.get("hard_decoy_progress_every_attempts", 250))),
                "--progress-max-interval-sec",
                str(float(prof.get("hard_decoy_progress_max_interval_sec", 30.0))),
                "--progress-json",
                hard_progress,
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
                hard_summary_json,
                "--out-md",
                f"{out_prefix}_hard_decoy_summary.md",
            ]
            _save_state(current={"status": "pre_stage_running"})
            pre_stage = _run(pre_cmd, env=dict(os.environ))
            if not bool(pre_stage.get("ok", False)):
                pre_stage_state.update({"done": False, "ok": False})
                _save_state(current={"status": "pre_stage_failed"})
                payload = {
                    "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
                    "pass": False,
                    "stopped": bool(_STOP_REQUESTED),
                    "failed_stage": "pre_hard_decoy_benchmark",
                    "profile_json": profile_json,
                    "command": pre_stage,
                    "runs": [],
                    "aggregate": [],
                    "failures": [],
                    "artifacts": {
                        "summary_json": f"{out_prefix}_summary.json",
                        "summary_md": f"{out_prefix}_summary.md",
                        "state_json": state_json,
                    },
                }
                payload = _attach_artifacts_abs(payload)
                with open(f"{out_prefix}_summary.json", "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2, ensure_ascii=False)
                _release_instance_lock(lock_meta)
                return payload
        pre_stage_state.update({"done": True, "ok": True})
        _save_state(current={"status": "pre_stage_done"})
        calib_ref_csv = hard_labels
        ranking_labels_csv = hard_labels
        eval_split_csv = hard_split
        ligand_csv = hard_labels
        if bool(prof.get("rebalance_ligand_csv_after_hard_decoy", True)):
            try:
                ligand_csv = _rebalance_ligand_csv_by_role(
                    labels_csv=hard_labels,
                    split_csv=hard_split,
                    out_csv=hard_labels_balanced,
                )
                ranking_labels_csv = ligand_csv
                calib_ref_csv = ligand_csv
            except Exception:
                pass

    stopped = bool(_STOP_REQUESTED)

    for pos_target in positive_targets:
        for size in sizes:
            for rep in range(1, repeats + 1):
                if bool(_STOP_REQUESTED):
                    stopped = True
                    break
                run_key = _run_key(int(pos_target), int(size), int(rep))
                attempts_used = int(attempt_store.get(run_key, 0) or 0)
                if run_key in completed_keys:
                    cached = row_store.get(run_key, {}) if isinstance(row_store, dict) else {}
                    cached_summary = str(cached.get("summary_json", "") or "").strip() if isinstance(cached, dict) else ""
                    cached_pass = bool(cached.get("pass", False)) if isinstance(cached, dict) else False
                    if cached_summary and os.path.exists(cached_summary) and cached_pass:
                        continue
                    if cached_summary and os.path.exists(cached_summary) and (not resume_retry_failed_runs):
                        continue
                    if cached_summary and os.path.exists(cached_summary) and (attempts_used >= int(max_attempts_per_run)):
                        continue
                    # Resume safety: key marked completed but summary missing/corrupt -> re-run this key.
                    completed_keys.discard(run_key)
                    row_store.pop(run_key, None)
                    fail_store.pop(run_key, None)
                run_tag = f"{date_tag}_p{int(pos_target)}_n{size}_r{rep}"
                run_prefix = f"{out_prefix}_p{int(pos_target)}_n{size}_r{rep}"
                run_ligand_csv = str(ligand_csv)
                run_calib_ref_csv = str(calib_ref_csv)
                run_ranking_labels_csv = str(ranking_labels_csv)
                run_eval_split_csv = str(eval_split_csv)
                positive_aug_stats: Dict[str, Any] = {"applied": False, "added_rows": 0}
                full_replicas_cfg = int(full.get("replicas", 0))
                replicas_match_size = bool(full.get("replicas_match_ligand_size", True))
                if replicas_match_size:
                    full_replicas = int(size)
                elif full_replicas_cfg > 0:
                    full_replicas = int(full_replicas_cfg)
                else:
                    full_replicas = int(size)

                full_jobs_cfg = int(full.get("jobs_per_target", 0))
                full_jobs_mode = str(full.get("jobs_per_target_mode", "split_total")).strip().lower()
                if full_jobs_cfg > 0:
                    full_jobs_per_target = int(full_jobs_cfg)
                elif full_jobs_mode in {"split_total", "split"}:
                    full_jobs_per_target = int(max(1, int(math.ceil(float(size) / float(target_count)))))
                else:
                    full_jobs_per_target = int(size)
                total_full_jobs = int(max(1, full_jobs_per_target * target_count))

                full_max_jobs_score_cfg = int(full.get("max_jobs_score", 0))
                if full_max_jobs_score_cfg > 0:
                    full_max_jobs_score = int(max(1, min(total_full_jobs, full_max_jobs_score_cfg)))
                else:
                    full_max_jobs_score = int(total_full_jobs)
                # Prevent silent score truncation when queue expands across multiple targets.
                # If enabled, stage3 scoring capacity is auto-raised to full queue size.
                if bool(prof.get("enforce_full_score_coverage", True)) and full_max_jobs_score < total_full_jobs:
                    full_max_jobs_score = int(total_full_jobs)

                gate_min_positive_count = int(max(int(gate.get("min_positive_count", 0)), int(pos_target)))
                gate_min_ood_positive_count = int(max(0, int(gate.get("min_ood_positive_count", 0))))
                run_calibration = bool(prof.get("run_calibration", True))
                ranking_score_col = str(
                    prof.get("ranking_score_col", prof.get("calibration_proxy_col", "binding_energy_mmpbsa_kcal_mol_proxy"))
                )
                default_prob_col = (
                    str(prof.get("calibration_out_col", "binding_energy_mmpbsa_kcal_mol_calibrated"))
                    if run_calibration
                    else ranking_score_col
                )
                ranking_probability_score_col = str(
                    prof.get("ranking_probability_score_col", default_prob_col)
                )
                stage1_min_eval_positive_keys = int(min(int(pos_target), int(size)))
                stage1_min_eval_positive_3d_ready_keys = int(
                    max(
                        0,
                        int(
                            prof.get(
                                "stage1_min_eval_positive_3d_ready_keys",
                                stage1_min_eval_positive_keys,
                            )
                        ),
                    )
                )
                cmd = [
                    sys.executable,
                    "tools/run_ligand_htvs_pipeline.py",
                    "--run-scope",
                    "full",
                    "--date-tag",
                    run_tag,
                    "--targets",
                    base_targets,
                    "--out-prefix",
                    run_prefix,
                    "--enforce-data-contract"
                    if bool(enforce_data_contract)
                    else "--no-enforce-data-contract",
                    "--data-contract-json",
                    str(data_contract_json),
                    "--auto-heavy-artifacts-root"
                    if bool(auto_heavy_artifacts_root)
                    else "--no-auto-heavy-artifacts-root",
                    "--ligand-csv",
                    str(run_ligand_csv),
                    "--target-native-csv",
                    str(prof.get("target_native_csv", "config/real_drug_targets_native_v1.csv")),
                    "--native-path-col",
                    str(prof.get("native_path_col", "native_pdb_path")),
                    "--csv-relax-3d"
                    if bool(prof.get("csv_relax_3d", True))
                    else "--no-csv-relax-3d",
                    "--csv-relax-max-iters",
                    str(int(prof.get("csv_relax_max_iters", 200))),
                    "--csv-relax-embed-seed",
                    str(int(prof.get("csv_relax_embed_seed", 13))),
                    "--csv-relax-workers",
                    str(int(prof.get("csv_relax_workers", 0))),
                    "--csv-smiles-cache-json",
                    str(prof.get("csv_smiles_cache_json", "runs/ligand_smiles_bead_cache.json")),
                    "--trajectory-engine-mode",
                    str(prof.get("trajectory_engine_mode", "rust_hip")),
                    "--stage3-min-frames",
                    str(int(prof.get("stage3_min_frames", 100))),
                    "--stage3-workers",
                    str(int(prof.get("stage3_workers", 0))),
                    "--stage3-parallel-threshold",
                    str(int(prof.get("stage3_parallel_threshold", 2))),
                    "--traj-npz-compression",
                    str(prof.get("traj_npz_compression", "store")),
                    "--calibration-reference-csv",
                    str(run_calib_ref_csv),
                    "--ranking-labels-csv",
                    str(run_ranking_labels_csv),
                    "--stage1-csv-prioritize-binders"
                    if bool(prof.get("stage1_csv_prioritize_binders", True))
                    else "--no-stage1-csv-prioritize-binders",
                    "--stage1-csv-binder-col",
                    str(prof.get("stage1_csv_binder_col", "is_binder")),
                    "--reuse-stage1-if-exists",
                    "--stage1-min-eval-positive-keys",
                    str(int(stage1_min_eval_positive_keys)),
                    "--stage1-min-eval-positive-3d-ready-keys",
                    str(int(stage1_min_eval_positive_3d_ready_keys)),
                    "--stage1-require-positive-3d-ready"
                    if bool(prof.get("stage1_require_positive_3d_ready", True))
                    else "--no-stage1-require-positive-3d-ready",
                    "--stage1-require-native-path-for-positive-check"
                    if bool(prof.get("stage1_require_native_path_for_positive_check", True))
                    else "--no-stage1-require-native-path-for-positive-check",
                    "--stage1-positive-check-labels-csv",
                    str(run_ranking_labels_csv),
                    "--stage1-positive-check-split-csv",
                    str(run_eval_split_csv),
                    "--stage1-positive-check-eval-roles",
                    str(prof.get("ranking_eval_roles", "eval")),
                    "--stage1-positive-check-binder-col",
                    str(prof.get("ranking_binder_col", "is_binder")),
                    "--ranking-score-col",
                    ranking_score_col,
                    "--ranking-probability-score-col",
                    ranking_probability_score_col,
                    "--eval-split-csv",
                    str(run_eval_split_csv),
                    "--calibration-fit-roles",
                    str(prof.get("calibration_fit_roles", "fit")),
                    "--calibration-min-fit-unique-keys",
                    str(int(prof.get("calibration_min_fit_unique_keys", 0))),
                    "--calibration-min-pairs-to-fit",
                    str(int(prof.get("calibration_min_pairs_to_fit", 0))),
                    "--ranking-eval-roles",
                    str(prof.get("ranking_eval_roles", "eval")),
                    "--ranking-ood-eval-roles",
                    str(prof.get("ranking_ood_eval_roles", "ood_eval")),
                    "--ranking-min-expected-score-coverage",
                    str(float(prof.get("ranking_min_expected_score_coverage", 1.0))),
                    "--require-split-for-calibration"
                    if bool(prof.get("require_split_for_calibration", False))
                    else "--no-require-split-for-calibration",
                    "--require-split-for-ranking"
                    if bool(prof.get("require_split_for_ranking", False))
                    else "--no-require-split-for-ranking",
                    "--require-ood-eval" if bool(prof.get("require_ood_eval", False)) else "--no-require-ood-eval",
                    "--enforce-zero-overlap" if bool(prof.get("enforce_zero_overlap", False)) else "--no-enforce-zero-overlap",
                    "--run-calibration" if run_calibration else "--no-run-calibration",
                    "--stage45-min-observed-eval-coverage-ratio",
                    str(float(prof.get("stage45_min_observed_eval_coverage_ratio", 0.99))),
                    "--stage45-min-observed-eval-positive-coverage-ratio",
                    str(float(prof.get("stage45_min_observed_eval_positive_coverage_ratio", 0.95))),
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
                    str(int(full_replicas)),
                    "--max-ligands-full",
                    str(int(size)),
                    "--jobs-per-target-full",
                    str(int(full_jobs_per_target)),
                    "--traj-frames-full",
                    str(int(full.get("traj_frames", 120))),
                    "--traj-write-every",
                    str(int(prof.get("traj_write_every", 1))),
                    "--traj-frame-output-format",
                    str(prof.get("traj_frame_output_format", "pdb_files")),
                    "--traj-npz-layout",
                    str(prof.get("traj_npz_layout", "flat_shard")),
                    "--traj-npz-shard-size",
                    str(int(prof.get("traj_npz_shard_size", 512))),
                    "--traj-writer-workers",
                    str(int(prof.get("traj_writer_workers", 1))),
                    "--traj-writer-mode",
                    str(prof.get("traj_writer_mode", "process")),
                    *_profile_stage2_runtime_args(prof),
                    *_profile_traj_prod_args(prof),
                    *_profile_residual_prototype_args(prof),
                    *_profile_score_reference_args(prof),
                    "--max-jobs-score-full",
                    str(int(full_max_jobs_score)),
                    "--traj-dynamic-core-fallback-on-oom"
                    if bool(prof.get("traj_dynamic_core_fallback_on_oom", False))
                    else "--no-traj-dynamic-core-fallback-on-oom",
                    "--traj-abort-on-runtime-error"
                    if bool(prof.get("traj_abort_on_runtime_error", True))
                    else "--no-traj-abort-on-runtime-error",
                    "--traj-abort-on-cpu-backend"
                    if bool(prof.get("traj_abort_on_cpu_backend", True))
                    else "--no-traj-abort-on-cpu-backend",
                    "--gate-min-frames",
                    str(int(gate.get("min_frames", 100))),
                    "--gate-max-mean-min-distance-A",
                    str(float(gate.get("max_mean_min_distance_A", 2.5))),
                    "--gate-mean-min-distance-source",
                    str(gate.get("mean_min_distance_source", "eval_unique_topk")),
                    "--gate-mean-min-distance-topk",
                    str(int(gate.get("mean_min_distance_topk", 200))),
                    "--gate-ranking-auc-min",
                    str(float(gate.get("ranking_auc_min", 0.9))),
                    "--gate-ranking-unique-auc-min",
                    str(float(gate.get("ranking_unique_auc_min", 0.9))),
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
                    str(float(gate.get("ef1_ci_lower_min", 1.0))),
                    "--gate-topk-k",
                    str(int(gate.get("topk_k", 10))),
                    "--gate-topk-hit-rate-min",
                    str(float(gate.get("topk_hit_rate_min", 0.8))),
                    "--gate-min-positive-count",
                    str(int(gate_min_positive_count)),
                    "--gate-min-ood-positive-count",
                    str(int(gate_min_ood_positive_count)),
                    "--gate-min-eval-unique-keys",
                    str(int(gate.get("min_eval_unique_keys", 0))),
                    "--gate-min-ood-unique-keys",
                    str(int(gate.get("min_ood_unique_keys", 0))),
                    "--gate-ranking-min-expected-score-coverage",
                    str(float(gate.get("ranking_min_expected_score_coverage", 1.0))),
                    "--gate-ranking-score-unique-ratio-min",
                    str(float(gate.get("ranking_score_unique_ratio_min", 0.05))),
                    "--gate-ranking-score-tie-ratio-max",
                    str(float(gate.get("ranking_score_tie_ratio_max", 0.95))),
                    "--gate-ranking-score-mode-ratio-max",
                    str(float(gate.get("ranking_score_mode_ratio_max", 0.95))),
                    "--gate-ranking-fail-on-orientation-suspect"
                    if bool(gate.get("ranking_fail_on_orientation_suspect", True))
                    else "--no-gate-ranking-fail-on-orientation-suspect",
                    "--ranking-bootstrap-n",
                    str(int(prof.get("ranking_bootstrap_n", 400))),
                    "--ranking-bootstrap-seed",
                    str(int(prof.get("ranking_bootstrap_seed", 7)) + rep),
                    "--ranking-bootstrap-bedroc-alpha",
                    str(float(prof.get("ranking_bootstrap_bedroc_alpha", 20.0))),
                    "--ranking-ece-bins",
                    str(int(prof.get("ranking_ece_bins", 10))),
                    "--ranking-probability-logit-scale",
                    str(float(prof.get("ranking_probability_logit_scale", 1.35))),
                    "--ranking-labels-driven-eval"
                    if bool(prof.get("ranking_labels_driven_eval", True))
                    else "--no-ranking-labels-driven-eval",
                    "--ranking-missing-score-policy",
                    str(prof.get("ranking_missing_score_policy", "worst")),
                    "--ranking-missing-score-worst-margin",
                    str(float(prof.get("ranking_missing_score_worst_margin", 1000.0))),
                    "--strict-fail-fast",
                    "--enforce-operational-gate",
                    "--gate-enforcement-mode",
                    str(gate_enforcement_mode),
                    "--enforce-strict-gate"
                    if bool(prof.get("enforce_strict_gate", False) or gate_enforcement_mode in {"strict", "both"})
                    else "--no-enforce-strict-gate",
                    "--strict-gate-min-frames",
                    str(int(strict_gate.get("min_frames", gate.get("min_frames", 100)))),
                    "--strict-gate-max-mean-min-distance-A",
                    str(float(strict_gate.get("max_mean_min_distance_A", gate.get("max_mean_min_distance_A", 2.5)))),
                    "--strict-gate-ranking-unique-auc-min",
                    str(float(strict_gate.get("ranking_unique_auc_min", gate.get("ranking_unique_auc_min", 0.9)))),
                    "--strict-gate-ranking-ood-auc-min",
                    str(float(strict_gate.get("ranking_ood_auc_min", gate.get("ranking_ood_auc_min", 0.85)))),
                    "--strict-gate-pr-auc-min",
                    str(float(strict_gate.get("pr_auc_min", gate.get("pr_auc_min", 0.60)))),
                    "--strict-gate-ef1-min",
                    str(float(strict_gate.get("ef1_min", gate.get("ef1_min", 1.25)))),
                    "--strict-gate-bedroc-min",
                    str(float(strict_gate.get("bedroc_min", gate.get("bedroc_min", 0.30)))),
                    "--strict-gate-brier-max",
                    str(float(strict_gate.get("brier_max", gate.get("brier_max", 0.30)))),
                    "--strict-gate-ece-max",
                    str(float(strict_gate.get("ece_max", gate.get("ece_max", 0.30)))),
                    "--strict-gate-roc-auc-ci-lower-min",
                    str(float(strict_gate.get("roc_auc_ci_lower_min", gate.get("roc_auc_ci_lower_min", 0.80)))),
                    "--strict-gate-pr-auc-ci-lower-min",
                    str(float(strict_gate.get("pr_auc_ci_lower_min", gate.get("pr_auc_ci_lower_min", 0.50)))),
                    "--strict-gate-ef1-ci-lower-min",
                    str(float(strict_gate.get("ef1_ci_lower_min", gate.get("ef1_ci_lower_min", 1.0)))),
                    "--strict-gate-topk-hit-rate-min",
                    str(float(strict_gate.get("topk_hit_rate_min", gate.get("topk_hit_rate_min", 0.8)))),
                    "--strict-gate-min-positive-count",
                    str(int(strict_gate.get("min_positive_count", gate_min_positive_count))),
                    "--strict-gate-min-ood-positive-count",
                    str(int(strict_gate.get("min_ood_positive_count", gate_min_ood_positive_count))),
                    "--strict-gate-ranking-min-expected-score-coverage",
                    str(
                        float(
                            strict_gate.get(
                                "ranking_min_expected_score_coverage",
                                gate.get("ranking_min_expected_score_coverage", 1.0),
                            )
                        )
                    ),
                    "--strict-gate-score-unique-ratio-min",
                    str(float(strict_gate.get("ranking_score_unique_ratio_min", gate.get("ranking_score_unique_ratio_min", 0.05)))),
                    "--strict-gate-score-tie-ratio-max",
                    str(float(strict_gate.get("ranking_score_tie_ratio_max", gate.get("ranking_score_tie_ratio_max", 0.95)))),
                    "--strict-gate-score-mode-ratio-max",
                    str(float(strict_gate.get("ranking_score_mode_ratio_max", gate.get("ranking_score_mode_ratio_max", 0.95)))),
                    "--strict-gate-fail-on-orientation-suspect"
                    if bool(strict_gate.get("ranking_fail_on_orientation_suspect", gate.get("ranking_fail_on_orientation_suspect", True)))
                    else "--no-strict-gate-fail-on-orientation-suspect",
                    "--traj-require-rust-hip" if bool(prof.get("require_rust_hip", True)) else "--no-traj-require-rust-hip",
                    "--no-dry-run",
                ]
                if "stage45_min_observed_fit_coverage_ratio" in prof:
                    cmd.extend(
                        [
                            "--stage45-min-observed-fit-coverage-ratio",
                            str(float(prof["stage45_min_observed_fit_coverage_ratio"])),
                        ]
                    )
                if heavy_artifacts_root:
                    cmd.extend(["--heavy-artifacts-root", str(heavy_artifacts_root)])
                if prof.get("ranking_missing_score_worst_value", None) is not None:
                    cmd.extend(
                        [
                            "--ranking-missing-score-worst-value",
                            str(float(prof.get("ranking_missing_score_worst_value"))),
                        ]
                    )
                sleep_now = float(retry_sleep_sec)
                run_done = False
                final_failed = False
                while not run_done:
                    if bool(_STOP_REQUESTED):
                        stopped = True
                        break
                    attempt_no = int(attempt_store.get(run_key, 0) or 0) + 1
                    attempt_store[run_key] = int(attempt_no)
                    _save_state(
                        current={
                            "status": "run_running",
                            "run_key": run_key,
                            "positive_count_target": int(pos_target),
                            "ligand_size": int(size),
                            "repeat": int(rep),
                            "run_prefix": run_prefix,
                            "attempt": int(attempt_no),
                            "max_attempts": int(max_attempts_per_run),
                        }
                    )

                    run_ligand_csv = str(ligand_csv)
                    run_calib_ref_csv = str(calib_ref_csv)
                    run_ranking_labels_csv = str(ranking_labels_csv)
                    run_eval_split_csv = str(eval_split_csv)
                    positive_aug_stats = {"applied": False, "added_rows": 0}
                    if int(pos_target) > 0 and bool(auto_augment_positive):
                        if (not run_eval_split_csv) or (not os.path.exists(run_eval_split_csv)):
                            raise FileNotFoundError("positive counter augmentation requires valid eval_split_csv")
                        if (not run_ranking_labels_csv) or (not os.path.exists(run_ranking_labels_csv)):
                            raise FileNotFoundError("positive counter augmentation requires valid ranking_labels_csv")
                        aug_labels_csv = f"{run_prefix}_labels_pos{int(pos_target)}.csv"
                        aug_split_csv = f"{run_prefix}_split_pos{int(pos_target)}.csv"
                        positive_aug_stats = _augment_eval_positive_count(
                            labels_csv=run_ranking_labels_csv,
                            split_csv=run_eval_split_csv,
                            out_labels_csv=aug_labels_csv,
                            out_split_csv=aug_split_csv,
                            min_positive_count=int(pos_target),
                            eval_roles=list(positive_eval_roles),
                        )
                        run_ligand_csv = str(aug_labels_csv)
                        run_calib_ref_csv = str(aug_labels_csv)
                        run_ranking_labels_csv = str(aug_labels_csv)
                        run_eval_split_csv = str(aug_split_csv)

                    cmd_run = list(cmd)
                    # Update per-attempt file paths in command payload.
                    for i, tok in enumerate(cmd_run):
                        if tok == "--ligand-csv" and i + 1 < len(cmd_run):
                            cmd_run[i + 1] = str(run_ligand_csv)
                        elif tok == "--calibration-reference-csv" and i + 1 < len(cmd_run):
                            cmd_run[i + 1] = str(run_calib_ref_csv)
                        elif tok == "--ranking-labels-csv" and i + 1 < len(cmd_run):
                            cmd_run[i + 1] = str(run_ranking_labels_csv)
                        elif tok == "--eval-split-csv" and i + 1 < len(cmd_run):
                            cmd_run[i + 1] = str(run_eval_split_csv)
                        elif tok == "--stage1-positive-check-labels-csv" and i + 1 < len(cmd_run):
                            cmd_run[i + 1] = str(run_ranking_labels_csv)
                        elif tok == "--stage1-positive-check-split-csv" and i + 1 < len(cmd_run):
                            cmd_run[i + 1] = str(run_eval_split_csv)
                    if (
                        bool(resume_stage3_only_on_retry)
                        and int(attempt_no) > 1
                        and _can_resume_stage3_only(run_prefix)
                    ):
                        cmd_run.append("--resume-stage3-only")

                    rec = _run(cmd_run, env=env)
                    summary_path = f"{run_prefix}_summary.json"
                    sum_payload = _read_json(summary_path) if os.path.exists(summary_path) else {}
                    gate_payload = ((sum_payload.get("stages") or {}).get("stage6_operational_gate") or {})
                    gate_strict_payload = ((sum_payload.get("stages") or {}).get("stage6_strict_gate") or {})
                    sla_payload = ((sum_payload.get("stages") or {}).get("stage8_sla") or {})
                    traj_prod_audit = _extract_traj_prod_audit_fields(sum_payload)
                    run_ok = bool(rec.get("ok", False)) and bool(sum_payload.get("pass", False))
                    row = {
                        "positive_count_target": int(pos_target),
                        "ligand_size": int(size),
                        "repeat": int(rep),
                        "attempt": int(attempt_no),
                        "max_attempts": int(max_attempts_per_run),
                        "pass": bool(run_ok),
                        "summary_json": summary_path,
                        "summary_json_abs": _abs_path(summary_path),
                        "positive_augmentation_applied": bool(positive_aug_stats.get("applied", False)),
                        "positive_augmentation_added_rows": int(positive_aug_stats.get("added_rows", 0) or 0),
                        "ranking_unique_auc": _safe_num(gate_payload.get("ranking_unique_auc")),
                        "ranking_ood_unique_auc": _safe_num(gate_payload.get("ranking_ood_unique_auc")),
                        "ranking_row_auc_aux": _safe_num(gate_payload.get("ranking_row_auc_aux")),
                        "ranking_pr_auc": _safe_num(gate_payload.get("ranking_pr_auc")),
                        "ranking_ef1": _safe_num(gate_payload.get("ranking_ef1")),
                        "ranking_bedroc": _safe_num(gate_payload.get("ranking_bedroc")),
                        "ranking_brier": _safe_num(gate_payload.get("ranking_brier")),
                        "ranking_ece": _safe_num(gate_payload.get("ranking_ece")),
                        "roc_auc_ci_low": _safe_num(gate_payload.get("ranking_roc_auc_ci_low")),
                        "pr_auc_ci_low": _safe_num(gate_payload.get("ranking_pr_auc_ci_low")),
                        "ef1_ci_low": _safe_num(gate_payload.get("ranking_ef1_ci_low")),
                        "topk_hit_rate": _safe_num(gate_payload.get("ranking_topk_hit_rate")),
                        "ranking_positive_count": _safe_num(gate_payload.get("ranking_positive_count")),
                        "ranking_ood_positive_count": _safe_num(gate_payload.get("ranking_ood_positive_count")),
                        "ranking_score_unique_ratio": _safe_num(gate_payload.get("ranking_score_unique_ratio")),
                        "ranking_score_tie_ratio": _safe_num(gate_payload.get("ranking_score_tie_ratio")),
                        "ranking_score_mode_ratio": _safe_num(gate_payload.get("ranking_score_mode_ratio")),
                        "ranking_expected_score_coverage_ratio": _safe_num(
                            gate_payload.get("ranking_expected_score_coverage_ratio")
                        ),
                        "operational_gate_pass": bool(gate_payload.get("pass", False)),
                        "strict_gate_pass": bool(gate_strict_payload.get("pass", True)),
                        "gate_enforcement_mode": str(sum_payload.get("gate_enforcement_mode", gate_enforcement_mode)),
                        "sla_total_latency_sec": _safe_num(sla_payload.get("total_latency_sec")),
                        "sla_queue_rate_stage2_rows_per_sec": _safe_num(sla_payload.get("queue_rate_stage2_rows_per_sec")),
                        "sla_queue_rate_stage3_rows_per_sec": _safe_num(sla_payload.get("queue_rate_stage3_rows_per_sec")),
                        "sla_gate_failure_rate_proxy": _safe_num(sla_payload.get("gate_failure_rate_proxy")),
                        "gate_min_positive_count": int(gate_min_positive_count),
                        "gate_min_ood_positive_count": int(gate_min_ood_positive_count),
                    }
                    row.update(traj_prod_audit)

                    if run_ok:
                        row_store[run_key] = row
                        completed_keys.add(run_key)
                        fail_store.pop(run_key, None)
                        _save_state(
                            current={
                                "status": "run_done",
                                "run_key": run_key,
                                "pass": True,
                                "summary_json": summary_path,
                                "attempt": int(attempt_no),
                            }
                        )
                        run_done = True
                        final_failed = False
                        break

                    fail_store[run_key] = {
                        "positive_count_target": int(pos_target),
                        "ligand_size": int(size),
                        "repeat": int(rep),
                        "attempt": int(attempt_no),
                        "max_attempts": int(max_attempts_per_run),
                        "command": rec,
                        "summary": sum_payload,
                    }
                    attempts_left = int(max_attempts_per_run - attempt_no)
                    if attempts_left > 0 and (not bool(_STOP_REQUESTED)):
                        _save_state(
                            current={
                                "status": "run_retry_wait",
                                "run_key": run_key,
                                "attempt": int(attempt_no),
                                "next_attempt": int(attempt_no + 1),
                                "max_attempts": int(max_attempts_per_run),
                                "sleep_sec": float(sleep_now),
                            }
                        )
                        if float(sleep_now) > 0.0:
                            time.sleep(float(sleep_now))
                        sleep_now = float(max(0.0, sleep_now * retry_backoff))
                        continue

                    row_store[run_key] = row
                    completed_keys.add(run_key)
                    _save_state(
                        current={
                            "status": "run_done",
                            "run_key": run_key,
                            "pass": False,
                            "summary_json": summary_path,
                            "attempt": int(attempt_no),
                            "exhausted": True,
                        }
                    )
                    run_done = True
                    final_failed = True
                    break

                if bool(_STOP_REQUESTED):
                    stopped = True
                    break
                if final_failed and bool(args.fail_fast):
                    fail_fast_triggered = True
                    break
            if fail_fast_triggered:
                break
            if stopped:
                break
        if fail_fast_triggered:
            break
        if stopped:
            break

    rows: List[Dict[str, Any]] = [row_store[k] for k in planned_keys if k in row_store]
    failures: List[Dict[str, Any]] = [fail_store[k] for k in planned_keys if k in fail_store]

    df = pd.DataFrame(rows)
    agg_rows: List[Dict[str, Any]] = []
    group_cols = ["ligand_size"]
    if "positive_count_target" in df.columns:
        group_cols = ["positive_count_target", "ligand_size"]
    for g_key, g in df.groupby(group_cols):
        rec: Dict[str, Any] = {"runs": int(len(g)), "pass_rate": float(g["pass"].mean())}
        if isinstance(g_key, tuple):
            rec["positive_count_target"] = int(g_key[0])
            rec["ligand_size"] = int(g_key[1])
        else:
            rec["ligand_size"] = int(g_key)
        for m in [
            "ranking_unique_auc",
            "ranking_ood_unique_auc",
            "ranking_pr_auc",
            "ranking_ef1",
            "ranking_bedroc",
            "ranking_brier",
            "ranking_ece",
            "roc_auc_ci_low",
            "pr_auc_ci_low",
            "ef1_ci_low",
            "topk_hit_rate",
            "ranking_positive_count",
            "ranking_ood_positive_count",
            "ranking_score_unique_ratio",
            "ranking_score_tie_ratio",
            "ranking_score_mode_ratio",
            "ranking_expected_score_coverage_ratio",
            "operational_gate_pass",
            "strict_gate_pass",
            "sla_total_latency_sec",
            "sla_queue_rate_stage2_rows_per_sec",
            "sla_queue_rate_stage3_rows_per_sec",
            "sla_gate_failure_rate_proxy",
            "traj_prod_effective_traj_frames",
            "traj_prod_effective_writer_workers",
            "traj_prod_effective_writer_max_pending",
            "traj_prod_effective_dynamic_adress_fraction",
            "traj_prod_effective_dynamic_adress_max_protein_residues",
            "traj_prod_effective_min_frames",
            "traj_prod_effective_early_stop_min_frames",
            "traj_prod_effective_early_stop_window",
            "traj_prod_effective_early_stop_contact_drift",
            "traj_prod_effective_early_stop_min_distance_drift_A",
            "traj_prod_effective_early_stop_max_mean_min_distance_A",
        ]:
            vals = [float(x) for x in g[m].dropna().tolist()]
            if vals:
                rec[f"{m}_mean"] = float(statistics.mean(vals))
                rec[f"{m}_min"] = float(min(vals))
                rec[f"{m}_max"] = float(max(vals))
        rec["traj_prod_enabled_runs"] = int(sum(1 for x in g["traj_prod_enabled"].tolist() if bool(x))) if "traj_prod_enabled" in g else 0
        rec["traj_prod_warning_runs"] = (
            int(sum(1 for x in g["traj_prod_warning_count"].tolist() if int(x or 0) > 0))
            if "traj_prod_warning_count" in g
            else 0
        )
        for src_col, dst_col in [
            ("traj_prod_profile_intent", "traj_prod_profile_intents"),
            ("traj_prod_requested_preset", "traj_prod_requested_presets"),
            ("traj_prod_resolved_preset", "traj_prod_resolved_presets"),
            ("traj_prod_strict_status", "traj_prod_strict_statuses"),
            ("traj_prod_effective_batch_autotune_candidates", "traj_prod_effective_batch_autotune_candidates"),
            ("traj_prod_effective_frame_budget_tiers", "traj_prod_effective_frame_budget_tiers"),
        ]:
            if src_col in g:
                uniq = sorted({str(x) for x in g[src_col].dropna().tolist() if str(x).strip()})
                rec[dst_col] = "|".join(uniq)
        if "traj_prod_hinted_families" in g:
            hinted: List[str] = []
            for item in g["traj_prod_hinted_families"].dropna().tolist():
                if isinstance(item, list):
                    hinted.extend(str(x) for x in item if str(x).strip())
            rec["traj_prod_hinted_families"] = "|".join(sorted(set(hinted)))
        agg_rows.append(rec)

    agg_df = pd.DataFrame(agg_rows)
    if not agg_df.empty:
        sort_cols = [c for c in ["positive_count_target", "ligand_size"] if c in agg_df.columns]
        if sort_cols:
            agg_df = agg_df.sort_values(sort_cols).reset_index(drop=True)
    completed_planned = int(sum(1 for k in planned_keys if k in completed_keys))
    total_planned = int(len(planned_keys))
    all_pass = bool(df["pass"].all()) if (not df.empty and completed_planned >= total_planned and not stopped) else False

    out_json = f"{out_prefix}_summary.json"
    out_csv = f"{out_prefix}_runs.csv"
    out_agg_csv = f"{out_prefix}_aggregate.csv"
    out_md = f"{out_prefix}_summary.md"

    _ensure_parent(out_json)
    df.to_csv(out_csv, index=False)
    agg_df.to_csv(out_agg_csv, index=False)

    payload = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "pass": bool(all_pass),
        "stopped": bool(stopped),
        "profile_json": profile_json,
        "traj_prod": _profile_traj_prod_summary(prof),
        "traj_prod_observability": _summarize_traj_prod_observability(rows),
        "ligand_sizes": sizes,
        "repeats": int(repeats),
        "planned_runs": int(total_planned),
        "completed_runs": int(completed_planned),
        "positive_count_targets": [int(x) for x in positive_targets],
        "positive_counter_auto_augment": bool(auto_augment_positive),
        "positive_counter_eval_roles": list(positive_eval_roles),
        "retry_policy": (prof.get("retry", {}) if isinstance(prof.get("retry"), dict) else {}),
        "retry_runtime": {
            "max_attempts_per_run": int(max_attempts_per_run),
            "retry_sleep_sec": float(retry_sleep_sec),
            "retry_backoff": float(retry_backoff),
            "resume_retry_failed_runs": bool(resume_retry_failed_runs),
            "resume_stage3_only_on_retry": bool(resume_stage3_only_on_retry),
        },
        "guarded_100k_readiness_preflight": guarded_100k_preflight,
        "stage_lock": {k: v for k, v in lock_meta.items() if k != "fd"},
        "pre_stage_hard_decoy": pre_stage,
        "calibration_reference_csv_effective": calib_ref_csv,
        "ranking_labels_csv_effective": ranking_labels_csv,
        "eval_split_csv_effective": eval_split_csv,
        "ligand_csv_effective": ligand_csv,
        "runs": rows,
        "aggregate": agg_rows,
        "failures": failures,
        "artifacts": {
            "runs_csv": out_csv,
            "aggregate_csv": out_agg_csv,
            "summary_json": out_json,
            "summary_md": out_md,
            "state_json": state_json,
        },
        "path_info": {
            "cwd": _abs_path("."),
            "out_prefix_abs": _abs_path(out_prefix),
            "summary_json_abs": _abs_path(out_json),
            "summary_md_abs": _abs_path(out_md),
            "runs_csv_abs": _abs_path(out_csv),
            "aggregate_csv_abs": _abs_path(out_agg_csv),
            "state_json_abs": _abs_path(state_json),
        },
    }
    payload = _attach_artifacts_abs(payload)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    if callable(_write_closeout_latest):
        try:
            _write_closeout_latest(
                summary_json=str(out_json),
                out_dir="runs",
                prefix="CLOSEOUT",
                symlink_latest=True,
            )
        except Exception:
            pass

    pre_stage_state.update({"done": bool(pre_stage_state.get("done", False)), "ok": bool(pre_stage.get("ok", False))})
    _save_state(
        current={
            "status": "finished",
            "pass": bool(all_pass),
            "stopped": bool(stopped),
            "completed_runs": int(completed_planned),
            "planned_runs": int(total_planned),
        },
        stopped=bool(stopped),
    )

    md_lines = [
        "# Ligand Stress Validation",
        "",
        f"- generated_at_local: {payload['generated_at_local']}",
        f"- pass: {payload['pass']}",
        f"- stopped: {payload['stopped']}",
        f"- profile_json: `{profile_json}`",
        f"- ligand_sizes: {sizes}",
        f"- repeats: {repeats}",
        f"- completed_runs: {payload['completed_runs']}/{payload['planned_runs']}",
        f"- positive_count_targets: {payload['positive_count_targets']}",
        f"- positive_counter_auto_augment: {payload['positive_counter_auto_augment']}",
        f"- pre_stage_hard_decoy_ok: {bool(pre_stage.get('ok', False))}",
        f"- ligand_csv_effective: `{ligand_csv}`",
        f"- eval_split_csv_effective: `{eval_split_csv}`",
        f"- runs_csv: `{out_csv}`",
        f"- aggregate_csv: `{out_agg_csv}`",
        f"- state_json: `{state_json}`",
        f"- summary_json_abs: `{payload.get('path_info', {}).get('summary_json_abs', '')}`",
        f"- runs_csv_abs: `{payload.get('path_info', {}).get('runs_csv_abs', '')}`",
        f"- aggregate_csv_abs: `{payload.get('path_info', {}).get('aggregate_csv_abs', '')}`",
        f"- failures: {len(failures)}",
    ]
    md_lines.extend(
        [
            "",
            *_traj_prod_markdown_lines(
                payload.get("traj_prod", {}),
                payload.get("traj_prod_observability", {}),
            ),
        ]
    )
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")

    _release_instance_lock(lock_meta)
    return payload


def build_parser() -> argparse.ArgumentParser:
    stamp = dt.date.today().isoformat()
    p = argparse.ArgumentParser(description="Run staged ligand scale-up validation (64->1k->5k->10k, repeated).")
    p.add_argument("--profile-json", type=str, default="config/ligand_htvs_nightly_strict_v1.json")
    p.add_argument("--ligand-sizes", type=str, default="64,1000,5000,10000")
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--targets", type=str, default="")
    p.add_argument("--date-tag", type=str, default=stamp)
    p.add_argument("--out-prefix", type=str, default=f"runs/ligand_stress_validation_{stamp}")
    p.add_argument("--single-instance", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--lock-file", type=str, default="")
    p.add_argument("--positive-count-sweep", type=str, default="")
    p.add_argument("--auto-augment-positive-count", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--resume-retry-failed-runs", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--state-json", type=str, default="")
    p.add_argument("--fail-fast", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--max-attempts-per-run", type=int, default=0)
    p.add_argument("--retry-sleep-sec", type=float, default=-1.0)
    p.add_argument("--retry-backoff", type=float, default=-1.0)
    p.add_argument("--heavy-artifacts-root", type=str, default="")
    p.add_argument("--auto-heavy-artifacts-root", action=argparse.BooleanOptionalAction, default=None)
    p.add_argument("--enforce-data-contract", action=argparse.BooleanOptionalAction, default=None)
    p.add_argument("--data-contract-json", type=str, default="")
    p.add_argument("--guarded-100k-readiness-json", type=str, default=DEFAULT_GPCR_GUARDED_100K_READINESS_JSON)
    p.add_argument("--enforce-guarded-100k-readiness", action=argparse.BooleanOptionalAction, default=None)
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    signal.signal(signal.SIGINT, _signal_stop)
    signal.signal(signal.SIGTERM, _signal_stop)
    args = build_parser().parse_args(argv)
    payload = run_stress(args)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if bool(payload.get("stopped", False)):
        raise SystemExit(130)
    if not bool(payload.get("pass", False)):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
