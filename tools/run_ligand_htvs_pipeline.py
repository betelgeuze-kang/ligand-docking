#!/usr/bin/env python3

from __future__ import annotations

import argparse
import atexit
import datetime as dt
import fcntl
import json
import math
import os
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

try:
    from tools.update_closeout_latest import write_closeout as _write_closeout_latest
except Exception:  # pragma: no cover
    _write_closeout_latest = None


def _run_cmd(cmd: List[str]) -> Dict[str, Any]:
    t0 = time.time()
    started = dt.datetime.now().isoformat(timespec="seconds")
    proc = subprocess.run(cmd, text=True, capture_output=True)
    t1 = time.time()
    ended = dt.datetime.now().isoformat(timespec="seconds")
    return {
        "cmd": cmd,
        "cmd_str": " ".join(cmd),
        "ok": bool(proc.returncode == 0),
        "returncode": int(proc.returncode),
        "started_at_local": started,
        "ended_at_local": ended,
        "duration_sec": float(max(t1 - t0, 0.0)),
        "stdout_tail": "\n".join((proc.stdout or "").splitlines()[-40:]),
        "stderr_tail": "\n".join((proc.stderr or "").splitlines()[-40:]),
    }


def _ensure_parent(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


def _acquire_instance_lock(lock_path: str) -> Dict[str, Any]:
    path = str(lock_path or "").strip()
    if not path:
        return {"ok": True, "enabled": False, "fd": None, "lock_path": ""}
    _ensure_parent(path)
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
        return {
            "ok": False,
            "enabled": True,
            "fd": None,
            "lock_path": os.path.abspath(path),
            "owner": owner,
        }
    os.ftruncate(fd, 0)
    os.lseek(fd, 0, os.SEEK_SET)
    os.write(fd, str(os.getpid()).encode("utf-8"))
    return {
        "ok": True,
        "enabled": True,
        "fd": fd,
        "lock_path": os.path.abspath(path),
        "owner": str(os.getpid()),
    }


def _release_instance_lock(lock: Dict[str, Any]) -> None:
    if not isinstance(lock, dict):
        return
    fd = lock.get("fd")
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


def _read_json_if_exists(path: str) -> Dict[str, Any]:
    src = str(path).strip()
    if (not src) or (not os.path.exists(src)):
        return {}
    try:
        with open(src, "r", encoding="utf-8") as f:
            obj = json.load(f)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _csv_rows_minus_header(path: str) -> int:
    src = str(path).strip()
    if (not src) or (not os.path.exists(src)):
        return 0
    try:
        with open(src, "r", encoding="utf-8", errors="ignore") as f:
            n = sum(1 for _ in f)
        return max(0, int(n - 1))
    except Exception:
        return 0


def _sanitize_run_name(path_like: str) -> str:
    name = os.path.basename(str(path_like).rstrip("/"))
    if not name:
        name = str(path_like).replace("/", "_")
    clean = "".join(ch if (ch.isalnum() or ch in {"-", "_", "."}) else "_" for ch in name)
    return clean or "ligand_htvs_run"


def _resolve_heavy_artifact_paths(
    *,
    out_prefix: str,
    heavy_root: str,
    subdir: str,
    auto_mount: bool,
) -> Dict[str, Any]:
    root = str(heavy_root).strip()
    if (not root) and bool(auto_mount):
        candidate = "/media/betelgeuze/ubuntu-1"
        if os.path.isdir(candidate):
            root = os.path.join(candidate, "md_runs")
    resolved: Dict[str, Any] = {
        "enabled": False,
        "root": "",
        "run_dir": "",
        "stage2_trajectory_root": "",
        "stage3_delivery_dir": "",
        "error": "",
    }
    if not root:
        return resolved
    try:
        run_name = _sanitize_run_name(subdir.strip() if str(subdir).strip() else out_prefix)
        run_dir = os.path.join(root, run_name)
        os.makedirs(run_dir, exist_ok=True)
        stage2_root = os.path.join(run_dir, "stage2_trajectory_frames")
        stage3_dir = os.path.join(run_dir, "stage3_delivery")
        os.makedirs(stage2_root, exist_ok=True)
        os.makedirs(stage3_dir, exist_ok=True)
        resolved.update(
            {
                "enabled": True,
                "root": root,
                "run_dir": run_dir,
                "stage2_trajectory_root": stage2_root,
                "stage3_delivery_dir": stage3_dir,
            }
        )
    except Exception as e:
        resolved["error"] = str(e)
    return resolved


def _validate_data_contract_input(args: argparse.Namespace) -> Dict[str, Any]:
    report: Dict[str, Any] = {
        "ok": True,
        "contract_json": str(args.data_contract_json),
        "errors": [],
        "warnings": [],
        "checks": {},
    }
    contract_path = str(args.data_contract_json).strip()
    contract = _read_json_if_exists(contract_path)
    if not contract:
        report["warnings"].append(f"contract not found or invalid json: {contract_path}")
        return report
    input_spec = contract.get("input", {}) if isinstance(contract.get("input"), dict) else {}
    checks: Dict[str, Any] = {}
    for key, csv_path in [
        ("ligand_csv", str(args.ligand_csv)),
        ("eval_split_csv", str(args.eval_split_csv)),
        ("ranking_labels_csv", str(args.ranking_labels_csv)),
    ]:
        req_cols = input_spec.get(f"{key}_required_cols", [])
        if not isinstance(req_cols, list) or len(req_cols) <= 0:
            continue
        req_cols = [str(c) for c in req_cols if str(c).strip()]
        src = str(csv_path).strip()
        row: Dict[str, Any] = {"path": src, "required_cols": req_cols, "present": False, "missing_cols": []}
        if not src:
            row["present"] = False
            row["missing_cols"] = list(req_cols)
            report["errors"].append(f"{key} path missing (required cols: {req_cols})")
            checks[key] = row
            continue
        if not os.path.exists(src):
            row["present"] = False
            row["missing_cols"] = list(req_cols)
            report["errors"].append(f"{key} file missing: {src}")
            checks[key] = row
            continue
        try:
            cols = [str(c) for c in pd.read_csv(src, nrows=0).columns.tolist()]
        except Exception as e:
            report["errors"].append(f"{key} failed to read header: {src} ({e})")
            checks[key] = row
            continue
        missing = [c for c in req_cols if c not in cols]
        row["present"] = True
        row["missing_cols"] = missing
        if missing:
            report["errors"].append(f"{key} missing columns {missing}: {src}")
        checks[key] = row
    report["checks"] = checks
    report["ok"] = len(report["errors"]) == 0
    return report


def _validate_data_contract_output(payload: Dict[str, Any], contract_path: str) -> Dict[str, Any]:
    report: Dict[str, Any] = {
        "ok": True,
        "contract_json": str(contract_path),
        "errors": [],
        "warnings": [],
        "checks": {},
    }
    contract = _read_json_if_exists(contract_path)
    if not contract:
        report["warnings"].append(f"contract not found or invalid json: {contract_path}")
        return report
    out_spec = contract.get("output", {}) if isinstance(contract.get("output"), dict) else {}
    req_top = out_spec.get("summary_required_top_keys", [])
    req_art = out_spec.get("artifact_required_keys", [])
    if isinstance(req_top, list) and req_top:
        miss_top = [k for k in req_top if k not in payload]
        report["checks"]["summary_required_top_keys"] = {"required": req_top, "missing": miss_top}
        if miss_top:
            report["errors"].append(f"summary missing required top keys: {miss_top}")
    art = payload.get("artifacts", {}) if isinstance(payload.get("artifacts"), dict) else {}
    if isinstance(req_art, list) and req_art:
        miss_art = [k for k in req_art if (k not in art or not str(art.get(k, "")).strip())]
        report["checks"]["artifact_required_keys"] = {"required": req_art, "missing": miss_art}
        if miss_art:
            report["errors"].append(f"artifacts missing required keys: {miss_art}")
    report["ok"] = len(report["errors"]) == 0
    return report


def _build_claim_split(gate_summary: Dict[str, Any], rank_payload: Dict[str, Any]) -> Dict[str, Any]:
    commercial_metrics = {
        "pass": bool(gate_summary.get("pass", False)),
        "ranking_unique_auc": gate_summary.get("ranking_unique_auc"),
        "ranking_ood_unique_auc": gate_summary.get("ranking_ood_unique_auc"),
        "ranking_pr_auc": gate_summary.get("ranking_pr_auc"),
        "ranking_ef1": gate_summary.get("ranking_ef1"),
        "ranking_bedroc": gate_summary.get("ranking_bedroc"),
        "ranking_brier": gate_summary.get("ranking_brier"),
        "ranking_ece": gate_summary.get("ranking_ece"),
        "ranking_topk_hit_rate": gate_summary.get("ranking_topk_hit_rate"),
        "ranking_roc_auc_ci_low": gate_summary.get("ranking_roc_auc_ci_low"),
        "ranking_pr_auc_ci_low": gate_summary.get("ranking_pr_auc_ci_low"),
        "ranking_ef1_ci_low": gate_summary.get("ranking_ef1_ci_low"),
        "failed_metrics": gate_summary.get("failed_metrics", []),
    }
    research_metrics = {
        "ranking_row_auc_aux": gate_summary.get("ranking_row_auc_aux"),
        "ranking_score_unique_ratio": gate_summary.get("ranking_score_unique_ratio"),
        "ranking_score_tie_ratio": gate_summary.get("ranking_score_tie_ratio"),
        "ranking_score_mode_ratio": gate_summary.get("ranking_score_mode_ratio"),
        "ranking_score_orientation_auc_delta": gate_summary.get("ranking_score_orientation_auc_delta"),
        "ranking_score_orientation_suspect": gate_summary.get("ranking_score_orientation_suspect"),
        "ranking_expected_score_coverage_ratio": gate_summary.get("ranking_expected_score_coverage_ratio"),
        "warnings": gate_summary.get("warnings", []),
    }
    metrics = rank_payload.get("metrics", {}) if isinstance(rank_payload.get("metrics"), dict) else {}
    metrics_unique = (
        rank_payload.get("metrics_unique", {}) if isinstance(rank_payload.get("metrics_unique"), dict) else {}
    )
    research_metrics["metrics_full"] = metrics
    research_metrics["metrics_unique"] = metrics_unique
    return {
        "summary": {
            "pass": bool(commercial_metrics["pass"]),
            "failed_metric_count": int(len(commercial_metrics.get("failed_metrics", []))),
        },
        "commercial_claim": commercial_metrics,
        "research_claim": research_metrics,
    }


def _duration_of(stage_rec: Any) -> float:
    if isinstance(stage_rec, dict):
        v = stage_rec.get("duration_sec", 0.0)
        if isinstance(v, (int, float)):
            return float(max(v, 0.0))
    return 0.0


_TRAJ_PROD_STAGE2_PRESETS: Dict[str, Dict[str, Any]] = {
    "default": {
        "traj_job_batch_autotune_candidates": "2,4,8,16",
        "traj_writer_workers": 2,
        "traj_writer_max_pending": 128,
        "traj_dynamic_adress_min_affinity": 0.79,
        "traj_dynamic_adress_max_protein_residues": 180,
        "traj_dynamic_adress_fraction": 0.13,
        "traj_dynamic_adress_base_radius_A": 5.8,
        "traj_dynamic_adress_affinity_radius_scale": 2.8,
        "traj_dynamic_adress_mw_radius_scale": 2.3,
        "traj_dynamic_adress_max_all_atom_radius_A": 7.4,
        "traj_dynamic_adress_max_atom_ratio": 0.08,
        "traj_prod_frame_budget_tiers": "0.90:1.00,0.75:0.84,0.60:0.68,0.00:0.54",
        "traj_prod_min_frames": {"smoke": 72, "full": 144},
        "traj_prod_early_stop_min_frames": {"smoke": 80, "full": 156},
        "traj_prod_early_stop_window": 12,
        "traj_prod_early_stop_contact_drift": 0.015,
        "traj_prod_early_stop_min_distance_drift_A": 0.12,
        "traj_prod_early_stop_max_mean_min_distance_A": 6.0,
    },
    "gpcr": {
        "traj_job_batch_autotune_candidates": "2,4,8,16",
        "traj_writer_workers": 2,
        "traj_writer_max_pending": 160,
        "traj_dynamic_adress_min_affinity": 0.80,
        "traj_dynamic_adress_max_protein_residues": 170,
        "traj_dynamic_adress_fraction": 0.12,
        "traj_dynamic_adress_base_radius_A": 5.6,
        "traj_dynamic_adress_affinity_radius_scale": 2.7,
        "traj_dynamic_adress_mw_radius_scale": 2.2,
        "traj_dynamic_adress_max_all_atom_radius_A": 7.2,
        "traj_dynamic_adress_max_atom_ratio": 0.08,
        "traj_prod_frame_budget_tiers": "0.90:1.00,0.75:0.82,0.60:0.66,0.00:0.52",
        "traj_prod_min_frames": {"smoke": 72, "full": 140},
        "traj_prod_early_stop_min_frames": {"smoke": 80, "full": 152},
        "traj_prod_early_stop_window": 12,
        "traj_prod_early_stop_contact_drift": 0.015,
        "traj_prod_early_stop_min_distance_drift_A": 0.12,
        "traj_prod_early_stop_max_mean_min_distance_A": 5.9,
    },
    "ion_trpv1": {
        "traj_job_batch_autotune_candidates": "4,8,16",
        "traj_writer_workers": 3,
        "traj_writer_max_pending": 256,
        "traj_dynamic_adress_min_affinity": 0.82,
        "traj_dynamic_adress_max_protein_residues": 150,
        "traj_dynamic_adress_fraction": 0.10,
        "traj_dynamic_adress_base_radius_A": 5.2,
        "traj_dynamic_adress_affinity_radius_scale": 2.5,
        "traj_dynamic_adress_mw_radius_scale": 2.1,
        "traj_dynamic_adress_max_all_atom_radius_A": 6.8,
        "traj_dynamic_adress_max_atom_ratio": 0.06,
        "traj_prod_frame_budget_tiers": "0.92:1.00,0.78:0.88,0.62:0.74,0.00:0.60",
        "traj_prod_min_frames": {"smoke": 84, "full": 168},
        "traj_prod_early_stop_min_frames": {"smoke": 92, "full": 184},
        "traj_prod_early_stop_window": 14,
        "traj_prod_early_stop_contact_drift": 0.012,
        "traj_prod_early_stop_min_distance_drift_A": 0.10,
        "traj_prod_early_stop_max_mean_min_distance_A": 5.8,
    },
    "kinase_protease": {
        "traj_job_batch_autotune_candidates": "2,4,8,16",
        "traj_writer_workers": 2,
        "traj_writer_max_pending": 128,
        "traj_dynamic_adress_min_affinity": 0.77,
        "traj_dynamic_adress_max_protein_residues": 160,
        "traj_dynamic_adress_fraction": 0.11,
        "traj_dynamic_adress_base_radius_A": 5.4,
        "traj_dynamic_adress_affinity_radius_scale": 2.6,
        "traj_dynamic_adress_mw_radius_scale": 2.1,
        "traj_dynamic_adress_max_all_atom_radius_A": 6.9,
        "traj_dynamic_adress_max_atom_ratio": 0.07,
        "traj_prod_frame_budget_tiers": "0.90:0.95,0.75:0.76,0.60:0.60,0.00:0.46",
        "traj_prod_min_frames": {"smoke": 64, "full": 128},
        "traj_prod_early_stop_min_frames": {"smoke": 72, "full": 140},
        "traj_prod_early_stop_window": 10,
        "traj_prod_early_stop_contact_drift": 0.018,
        "traj_prod_early_stop_min_distance_drift_A": 0.14,
        "traj_prod_early_stop_max_mean_min_distance_A": 6.2,
    },
}


def _normalize_traj_prod_stage2_preset(value: Any) -> str:
    raw = str(value or "").strip().lower().replace("-", "_").replace("/", "_")
    aliases = {
        "": "off",
        "none": "off",
        "false": "off",
        "ion": "ion_trpv1",
        "trpv1": "ion_trpv1",
        "ion_channel": "ion_trpv1",
        "ion_channels": "ion_trpv1",
        "kinase": "kinase_protease",
        "protease": "kinase_protease",
    }
    normalized = aliases.get(raw, raw)
    allowed = {"off", "auto", "default", "gpcr", "ion_trpv1", "kinase_protease"}
    return normalized if normalized in allowed else "default"


def _infer_traj_prod_stage2_preset_family(args: argparse.Namespace) -> str:
    hinted_families = _traj_prod_stage2_target_family_hints(args)
    for family in hinted_families:
        if family in {"ion_trpv1", "gpcr", "kinase_protease"}:
            return family
    return "default"


def _traj_prod_stage2_target_family_hints(args: argparse.Namespace) -> List[str]:
    joined = " ".join(
        [
            str(getattr(args, attr, "") or "").strip().lower()
            for attr in ("targets", "target_native_csv", "leakage_target_meta_csv", "out_prefix")
            if str(getattr(args, attr, "") or "").strip()
        ]
    )
    families: List[str] = []
    if any(tok in joined for tok in ("trpv1", "ion_channel", "ion channel")):
        families.append("ion_trpv1")
    if "gpcr" in joined:
        families.append("gpcr")
    if any(tok in joined for tok in ("kinase", "protease")):
        families.append("kinase_protease")
    if not families:
        families.append("default")
    return families


def _traj_stage2_runtime_settings(args: argparse.Namespace, *, mode: str) -> Dict[str, Any]:
    normalized_mode = "smoke" if str(mode) == "smoke" else "full"
    base_traj_frames = int(
        getattr(
            args,
            "traj_frames_smoke" if normalized_mode == "smoke" else "traj_frames_full",
            120 if normalized_mode == "smoke" else 300,
        )
    )
    settings: Dict[str, Any] = {
        "traj_frames": base_traj_frames,
        "traj_job_batch_autotune_candidates": str(getattr(args, "traj_job_batch_autotune_candidates", "1,2,4,8")),
        "traj_writer_workers": int(getattr(args, "traj_writer_workers", 1)),
        "traj_writer_max_pending": int(getattr(args, "traj_writer_max_pending", 64)),
        "traj_dynamic_adress_min_affinity": float(getattr(args, "traj_dynamic_adress_min_affinity", 0.78)),
        "traj_dynamic_adress_max_protein_residues": int(
            getattr(args, "traj_dynamic_adress_max_protein_residues", 200)
        ),
        "traj_dynamic_adress_fraction": float(getattr(args, "traj_dynamic_adress_fraction", 0.15)),
        "traj_dynamic_adress_base_radius_A": float(getattr(args, "traj_dynamic_adress_base_radius_A", 6.0)),
        "traj_dynamic_adress_affinity_radius_scale": float(
            getattr(args, "traj_dynamic_adress_affinity_radius_scale", 3.0)
        ),
        "traj_dynamic_adress_mw_radius_scale": float(getattr(args, "traj_dynamic_adress_mw_radius_scale", 2.5)),
        "traj_dynamic_adress_max_all_atom_radius_A": float(
            getattr(args, "traj_dynamic_adress_max_all_atom_radius_A", 8.0)
        ),
        "traj_dynamic_adress_max_atom_ratio": float(getattr(args, "traj_dynamic_adress_max_atom_ratio", 0.10)),
        "traj_prod_frame_budget_tiers": str(
            getattr(args, "traj_prod_frame_budget_tiers", "0.90:1.00,0.75:0.85,0.60:0.70,0.00:0.55")
        ),
        "traj_prod_min_frames": 0,
        "traj_prod_early_stop_min_frames": 0,
        "traj_prod_early_stop_window": int(getattr(args, "traj_prod_early_stop_window", 12)),
        "traj_prod_early_stop_contact_drift": float(getattr(args, "traj_prod_early_stop_contact_drift", 0.015)),
        "traj_prod_early_stop_min_distance_drift_A": float(
            getattr(args, "traj_prod_early_stop_min_distance_drift_A", 0.12)
        ),
        "traj_prod_early_stop_max_mean_min_distance_A": float(
            getattr(args, "traj_prod_early_stop_max_mean_min_distance_A", 6.0)
        ),
    }
    settings["traj_prod_min_frames"] = int(_traj_prod_min_frames(args, normalized_mode, settings["traj_frames"]))
    settings["traj_prod_early_stop_min_frames"] = int(
        _traj_prod_early_stop_min_frames(args, normalized_mode, settings["traj_frames"])
    )
    explicit_runtime_overrides: Dict[str, Any] = {}
    if str(getattr(args, "traj_job_batch_autotune_candidates", "1,2,4,8")) != "1,2,4,8":
        explicit_runtime_overrides["traj_job_batch_autotune_candidates"] = str(
            getattr(args, "traj_job_batch_autotune_candidates")
        )
    if int(getattr(args, "traj_writer_workers", 1)) != 1:
        explicit_runtime_overrides["traj_writer_workers"] = int(getattr(args, "traj_writer_workers"))
    if int(getattr(args, "traj_writer_max_pending", 64)) != 64:
        explicit_runtime_overrides["traj_writer_max_pending"] = int(getattr(args, "traj_writer_max_pending"))
    selected = _normalize_traj_prod_stage2_preset(getattr(args, "traj_prod_stage2_preset", "off"))
    resolved = _infer_traj_prod_stage2_preset_family(args) if selected == "auto" else selected
    overrides: Dict[str, Any] = {}
    if resolved != "off":
        preset = _TRAJ_PROD_STAGE2_PRESETS.get(resolved, _TRAJ_PROD_STAGE2_PRESETS["default"])
        for key, value in preset.items():
            if key in {"traj_prod_min_frames", "traj_prod_early_stop_min_frames"}:
                mode_frames = value.get(normalized_mode) if isinstance(value, dict) else value
                overrides[key] = int(mode_frames)
            else:
                overrides[key] = value
        settings.update(overrides)
        settings.update(explicit_runtime_overrides)
    settings["traj_prod_stage2_preset"] = {
        "enabled": bool(resolved != "off"),
        "requested": selected,
        "resolved": resolved,
        "mode": normalized_mode,
        "overrides": overrides,
    }
    return settings


def _traj_prod_stage2_preset_diagnostics(args: argparse.Namespace) -> Dict[str, Any]:
    requested = _normalize_traj_prod_stage2_preset(getattr(args, "traj_prod_stage2_preset", "off"))
    hinted_families = _traj_prod_stage2_target_family_hints(args)
    resolved = _infer_traj_prod_stage2_preset_family(args) if requested == "auto" else requested
    warnings: List[str] = []
    if requested != "off" and (not bool(getattr(args, "traj_prod_speedpack", False))):
        warnings.append("traj_prod_stage2_preset is enabled while traj_prod_speedpack is off; preset affects stage2 runtime knobs but not adaptive frame budget or early stop.")
    if requested == "auto" and resolved == "default":
        warnings.append("traj_prod_stage2_preset auto mode fell back to default because no target-family hint was detected.")
    if requested not in {"off", "auto", "default"} and resolved not in set(hinted_families):
        warnings.append(
            f"traj_prod_stage2_preset={requested} does not match detected target-family hints {sorted(set(hinted_families))}; using explicit preset."
        )
    strict_enabled = bool(getattr(args, "traj_prod_stage2_preset_strict", False))
    strict_error = ""
    if strict_enabled:
        non_default_hints = sorted({fam for fam in hinted_families if fam != "default"})
        if requested == "auto" and len(non_default_hints) > 1:
            strict_error = (
                "traj_prod_stage2_preset strict preflight rejected mixed-family auto inference; "
                f"detected families={non_default_hints}. Choose an explicit preset."
            )
        elif requested not in {"off", "auto", "default"} and non_default_hints and requested not in non_default_hints:
            strict_error = (
                "traj_prod_stage2_preset strict preflight rejected explicit preset mismatch; "
                f"requested={requested}, detected={non_default_hints}."
            )
    return {
        "requested": requested,
        "resolved": resolved,
        "hinted_families": hinted_families,
        "strict_enabled": strict_enabled,
        "warnings": warnings,
        "error": strict_error,
    }


def _traj_prod_runtime_summary(args: argparse.Namespace, diagnostics: Dict[str, Any]) -> Dict[str, Any]:
    requested = str(diagnostics.get("requested", "off") or "off")
    resolved = str(diagnostics.get("resolved", requested) or requested)
    profile_intent = str(getattr(args, "traj_prod_profile_intent", "") or "").strip()
    speedpack = bool(getattr(args, "traj_prod_speedpack", False))
    adaptive_frame_budget = bool(getattr(args, "traj_prod_adaptive_frame_budget", True))
    early_stop = bool(getattr(args, "traj_prod_early_stop_enabled", False))
    light_artifacts = bool(getattr(args, "traj_prod_light_artifacts", True))
    enabled = bool(
        requested != "off"
        or speedpack
        or early_stop
        or (light_artifacts and speedpack)
    )
    warnings = [str(x) for x in diagnostics.get("warnings", []) if str(x).strip()]
    intent_warning = ""
    if enabled and (not profile_intent):
        intent_warning = "traj_prod knobs are enabled without traj_prod_profile_intent; auditability is reduced."
        warnings = [*warnings, intent_warning]
    return {
        "enabled": bool(enabled),
        "profile_intent": profile_intent,
        "requested_preset": requested,
        "resolved_preset": resolved,
        "strict": bool(diagnostics.get("strict_enabled", False)),
        "speedpack": bool(speedpack),
        "adaptive_frame_budget": bool(adaptive_frame_budget),
        "early_stop": bool(early_stop),
        "light_artifacts": bool(light_artifacts),
        "light_progress_every_jobs": int(max(1, int(getattr(args, "traj_prod_light_progress_every_jobs", 250)))),
        "warnings": warnings,
        "error": str(diagnostics.get("error", "") or ""),
        "hinted_families": [str(x) for x in diagnostics.get("hinted_families", []) if str(x).strip()],
        "intent_warning": intent_warning,
    }


def _traj_prod_operational_summary(
    *,
    traj_prod: Optional[Dict[str, Any]],
    traj_stage2_settings: Optional[Dict[str, Any]],
    traj_stage2_diag: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    prod = dict(traj_prod) if isinstance(traj_prod, dict) else {}
    settings = dict(traj_stage2_settings) if isinstance(traj_stage2_settings, dict) else {}
    diag = dict(traj_stage2_diag) if isinstance(traj_stage2_diag, dict) else {}
    strict_error = str(diag.get("error", "") or "")
    warnings = [str(x) for x in diag.get("warnings", []) if str(x).strip()]
    strict_status = "error" if strict_error else ("warn" if warnings else "ok")
    out = {
        "enabled": bool(prod.get("enabled", False)),
        "profile_intent": str(prod.get("profile_intent", "") or ""),
        "requested_preset": str(prod.get("requested_preset", diag.get("requested", "off")) or "off"),
        "resolved_preset": str(prod.get("resolved_preset", diag.get("resolved", "off")) or "off"),
        "strict_enabled": bool(prod.get("strict", diag.get("strict_enabled", False))),
        "strict_status": strict_status,
        "strict_error": strict_error,
        "warning_count": int(len(warnings)),
        "warnings": warnings,
        "hinted_families": [str(x) for x in diag.get("hinted_families", prod.get("hinted_families", [])) if str(x).strip()],
        "speedpack": bool(prod.get("speedpack", False)),
        "adaptive_frame_budget": bool(prod.get("adaptive_frame_budget", False)),
        "early_stop": bool(prod.get("early_stop", False)),
        "light_artifacts": bool(prod.get("light_artifacts", False)),
        "light_progress_every_jobs": int(max(1, int(prod.get("light_progress_every_jobs", 250) or 250))),
        "effective_traj_frames": int(max(1, int(settings.get("traj_frames", 0) or 0))) if settings else None,
        "effective_batch_autotune_candidates": str(settings.get("traj_job_batch_autotune_candidates", "") or ""),
        "effective_writer_workers": int(settings.get("traj_writer_workers", 0)) if settings else None,
        "effective_writer_max_pending": int(settings.get("traj_writer_max_pending", 0)) if settings else None,
        "effective_dynamic_adress_fraction": (
            float(settings.get("traj_dynamic_adress_fraction")) if settings and settings.get("traj_dynamic_adress_fraction") is not None else None
        ),
        "effective_dynamic_adress_max_protein_residues": (
            int(settings.get("traj_dynamic_adress_max_protein_residues")) if settings and settings.get("traj_dynamic_adress_max_protein_residues") is not None else None
        ),
        "effective_frame_budget_tiers": str(settings.get("traj_prod_frame_budget_tiers", "") or ""),
        "effective_min_frames": int(settings.get("traj_prod_min_frames", 0)) if settings else None,
        "effective_early_stop_min_frames": int(settings.get("traj_prod_early_stop_min_frames", 0)) if settings else None,
        "effective_early_stop_window": int(settings.get("traj_prod_early_stop_window", 0)) if settings else None,
        "effective_early_stop_contact_drift": (
            float(settings.get("traj_prod_early_stop_contact_drift")) if settings and settings.get("traj_prod_early_stop_contact_drift") is not None else None
        ),
        "effective_early_stop_min_distance_drift_A": (
            float(settings.get("traj_prod_early_stop_min_distance_drift_A")) if settings and settings.get("traj_prod_early_stop_min_distance_drift_A") is not None else None
        ),
        "effective_early_stop_max_mean_min_distance_A": (
            float(settings.get("traj_prod_early_stop_max_mean_min_distance_A")) if settings and settings.get("traj_prod_early_stop_max_mean_min_distance_A") is not None else None
        ),
    }
    return out


def _traj_prod_markdown_lines(
    *,
    traj_prod: Optional[Dict[str, Any]],
    traj_stage2_settings: Optional[Dict[str, Any]],
    traj_stage2_diag: Optional[Dict[str, Any]],
    heading: str = "## Production Stage2",
) -> List[str]:
    op = _traj_prod_operational_summary(
        traj_prod=traj_prod,
        traj_stage2_settings=traj_stage2_settings,
        traj_stage2_diag=traj_stage2_diag,
    )
    if not op:
        return []
    lines = [
        heading,
        "",
        f"- traj_prod_enabled: {op.get('enabled')}",
        f"- traj_prod_profile_intent: `{str(op.get('profile_intent', '') or '')}`",
        f"- traj_prod_requested_preset: `{str(op.get('requested_preset', '') or '')}`",
        f"- traj_prod_resolved_preset: `{str(op.get('resolved_preset', '') or '')}`",
        f"- traj_prod_strict_enabled: {op.get('strict_enabled')}",
        f"- traj_prod_strict_status: `{str(op.get('strict_status', '') or '')}`",
        f"- traj_prod_warning_count: {op.get('warning_count')}",
        f"- traj_prod_hinted_families: `{op.get('hinted_families')}`",
        f"- traj_prod_speedpack: {op.get('speedpack')}",
        f"- traj_prod_adaptive_frame_budget: {op.get('adaptive_frame_budget')}",
        f"- traj_prod_early_stop: {op.get('early_stop')}",
        f"- traj_prod_light_artifacts: {op.get('light_artifacts')}",
        f"- traj_prod_light_progress_every_jobs: {op.get('light_progress_every_jobs')}",
        "",
        "### Effective Runtime",
        "",
        f"- effective_traj_frames: {op.get('effective_traj_frames')}",
        f"- effective_batch_autotune_candidates: `{str(op.get('effective_batch_autotune_candidates', '') or '')}`",
        f"- effective_writer_workers: {op.get('effective_writer_workers')}",
        f"- effective_writer_max_pending: {op.get('effective_writer_max_pending')}",
        f"- effective_dynamic_adress_fraction: {op.get('effective_dynamic_adress_fraction')}",
        f"- effective_dynamic_adress_max_protein_residues: {op.get('effective_dynamic_adress_max_protein_residues')}",
        f"- effective_frame_budget_tiers: `{str(op.get('effective_frame_budget_tiers', '') or '')}`",
        f"- effective_min_frames: {op.get('effective_min_frames')}",
        f"- effective_early_stop_min_frames: {op.get('effective_early_stop_min_frames')}",
        f"- effective_early_stop_window: {op.get('effective_early_stop_window')}",
        f"- effective_early_stop_contact_drift: {op.get('effective_early_stop_contact_drift')}",
        f"- effective_early_stop_min_distance_drift_A: {op.get('effective_early_stop_min_distance_drift_A')}",
        f"- effective_early_stop_max_mean_min_distance_A: {op.get('effective_early_stop_max_mean_min_distance_A')}",
    ]
    strict_error = str(op.get("strict_error", "") or "").strip()
    if strict_error:
        lines.extend(["", f"- traj_prod_strict_error: `{strict_error}`"])
    warnings = [str(x) for x in op.get("warnings", []) if str(x).strip()]
    if warnings:
        lines.extend(["", f"- traj_prod_warnings: `{warnings}`"])
    return lines


def _traj_stage2_engine_telemetry(summary_json: str) -> Dict[str, Any]:
    src = str(summary_json or "").strip()
    payload = _read_json_if_exists(src) if src else {}
    if not payload:
        return {}
    artifacts = payload.get("artifacts", {}) if isinstance(payload.get("artifacts"), dict) else {}
    prod_light_effects = payload.get("prod_light_effects", {}) if isinstance(payload.get("prod_light_effects"), dict) else {}
    out: Dict[str, Any] = {
        "summary_json_present": True,
        "prod_mode": bool(payload.get("prod_mode", False)),
        "prod_light_artifacts": bool(payload.get("prod_light_artifacts", False)),
        "prod_adaptive_frame_budget": bool(payload.get("prod_adaptive_frame_budget", False)),
        "prod_early_stop": bool(payload.get("prod_early_stop", False)),
        "prod_frame_budget_applied_count": int(payload.get("prod_frame_budget_applied_count", 0) or 0),
        "prod_early_stop_batch_count": int(payload.get("prod_early_stop_batch_count", 0) or 0),
        "prod_early_stop_row_count": int(payload.get("prod_early_stop_row_count", 0) or 0),
        "mean_sim_frames_count": (
            float(payload.get("mean_sim_frames_count")) if payload.get("mean_sim_frames_count") is not None else None
        ),
        "mean_frames_effective_cap": (
            float(payload.get("mean_frames_effective_cap")) if payload.get("mean_frames_effective_cap") is not None else None
        ),
        "job_batch_derate_count": int(payload.get("job_batch_derate_count", 0) or 0),
        "job_batch_size": int(payload.get("job_batch_size", 0) or 0),
        "writer_workers": int(payload.get("writer_workers", 0) or 0),
        "writer_max_pending": int(payload.get("writer_max_pending", 0) or 0),
        "progress_every_jobs": int(payload.get("progress_every_jobs", 0) or 0),
        "target_tail_csv_present": bool(str(artifacts.get("target_tail_csv", "")).strip()),
        "manifest_chunks_dir_present": bool(str(artifacts.get("manifest_chunks_dir", "")).strip()),
        "summary_md_present": bool(str(artifacts.get("summary_md", "")).strip()),
        "prod_light_effects": prod_light_effects,
    }
    return out


def _physics_refinement_telemetry(summary_json: str) -> Dict[str, Any]:
    src = str(summary_json or "").strip()
    payload = _read_json_if_exists(src) if src else {}
    if not payload:
        return {}
    artifacts = payload.get("artifacts", {}) if isinstance(payload.get("artifacts"), dict) else {}
    selected_metrics = payload.get("selected_metrics", {}) if isinstance(payload.get("selected_metrics"), dict) else {}
    out: Dict[str, Any] = {
        "summary_json_present": True,
        "enabled": bool(payload.get("refinement_enabled", False)),
        "schema_version": str(payload.get("refinement_schema_version", "") or ""),
        "mode": str(payload.get("refinement_mode", "") or ""),
        "backend": str(payload.get("refinement_backend", "") or ""),
        "score_col_used": str(payload.get("score_col_used", "") or ""),
        "base_proxy_col_used": str(payload.get("base_proxy_col_used", "") or ""),
        "refined_energy_col": str(payload.get("refined_energy_col", "") or ""),
        "refined_rank_col": str(payload.get("refined_rank_col", "") or ""),
        "selected_count": int(payload.get("selected_count", 0) or 0),
        "selected_fraction": (
            float(payload.get("selected_fraction")) if payload.get("selected_fraction") is not None else None
        ),
        "selected_target_count": int(payload.get("selected_target_count", 0) or 0),
        "warnings": [str(x) for x in payload.get("warnings", []) if str(x).strip()],
        "selected_metrics": selected_metrics,
        "shortlist_csv_present": bool(str(artifacts.get("shortlist_csv", "")).strip()),
        "shortlist_json_present": bool(str(artifacts.get("shortlist_json", "")).strip()),
        "summary_md_present": bool(str(artifacts.get("out_md", "")).strip()),
    }
    return out


def _physics_refinement_markdown_lines(
    physics_refinement: Optional[Dict[str, Any]],
    *,
    heading: str = "## Physics Refinement",
) -> List[str]:
    info = dict(physics_refinement) if isinstance(physics_refinement, dict) else {}
    if not info:
        return []
    lines = [
        heading,
        "",
        f"- physics_refinement_enabled: {info.get('enabled')}",
        f"- physics_refinement_use_refined_scores_downstream: {info.get('use_refined_scores_downstream')}",
        f"- physics_refinement_use_refined_proxy_for_calibration: {info.get('use_refined_proxy_for_calibration')}",
        f"- physics_refinement_mode: `{str(info.get('refinement_mode', '') or '')}`",
        f"- physics_refinement_backend: `{str(info.get('refinement_backend', '') or '')}`",
        f"- physics_refinement_score_col_used: `{str(info.get('score_col_used', '') or '')}`",
        f"- physics_refinement_base_proxy_col_used: `{str(info.get('base_proxy_col_used', '') or '')}`",
        f"- physics_refinement_refined_energy_col: `{str(info.get('refined_energy_col', '') or '')}`",
        f"- physics_refinement_refined_rank_col: `{str(info.get('refined_rank_col', '') or '')}`",
        f"- physics_refinement_selected_count: {info.get('selected_count')}",
        f"- physics_refinement_selected_fraction: {info.get('selected_fraction')}",
        f"- physics_refinement_downstream_scores_csv: `{str(info.get('downstream_scores_csv', '') or '')}`",
        f"- physics_refinement_summary_json: `{str(info.get('summary_json', '') or '')}`",
        f"- physics_refinement_shortlist_csv: `{str(info.get('shortlist_csv', '') or '')}`",
    ]
    metrics = info.get("selected_metrics", {}) if isinstance(info.get("selected_metrics"), dict) else {}
    if metrics:
        lines.extend(
            [
                "",
                "### Selected Metrics",
                "",
                f"- mean_refined_energy_kcal_mol: {metrics.get('mean_refined_energy_kcal_mol')}",
                f"- mean_rank_score: {metrics.get('mean_rank_score')}",
                f"- mean_delta_kcal_mol: {metrics.get('mean_delta_kcal_mol')}",
                f"- mean_confidence: {metrics.get('mean_confidence')}",
                f"- max_delta_kcal_mol: {metrics.get('max_delta_kcal_mol')}",
            ]
        )
    warnings = [str(x) for x in info.get("warnings", []) if str(x).strip()]
    if warnings:
        lines.extend(["", f"- physics_refinement_warnings: `{warnings}`"])
    return lines


def _traj_prod_early_stop_min_frames(args: argparse.Namespace, mode: str, traj_frames: int) -> int:
    raw = (
        int(getattr(args, "traj_prod_early_stop_min_frames_smoke", traj_frames))
        if str(mode) == "smoke"
        else int(getattr(args, "traj_prod_early_stop_min_frames_full", traj_frames))
    )
    return int(min(max(1, raw), max(1, int(traj_frames))))


def _traj_prod_min_frames(args: argparse.Namespace, mode: str, traj_frames: int) -> int:
    raw = (
        int(getattr(args, "traj_prod_min_frames_smoke", traj_frames))
        if str(mode) == "smoke"
        else int(getattr(args, "traj_prod_min_frames_full", traj_frames))
    )
    return int(min(max(1, raw), max(1, int(traj_frames))))


def _traj_prod_stage2_args(args: argparse.Namespace, *, mode: str, traj_frames: int) -> List[str]:
    if not bool(getattr(args, "traj_prod_speedpack", False)):
        return []
    traj_stage2_settings = _traj_stage2_runtime_settings(args, mode=mode)
    effective_traj_frames = int(max(1, int(traj_frames or traj_stage2_settings["traj_frames"])))
    out = [
        "--prod-mode",
        "--prod-min-frames",
        str(int(min(max(1, int(traj_stage2_settings["traj_prod_min_frames"])), effective_traj_frames))),
    ]
    if bool(getattr(args, "traj_prod_adaptive_frame_budget", True)):
        out.extend(
            [
                "--prod-adaptive-frame-budget",
                "--prod-frame-budget-tiers",
                str(traj_stage2_settings["traj_prod_frame_budget_tiers"]),
            ]
        )
    if bool(getattr(args, "traj_prod_early_stop_enabled", False)):
        out.extend(
            [
                "--prod-early-stop",
                "--prod-early-stop-min-frames",
                str(
                    int(
                        min(
                            max(1, int(traj_stage2_settings["traj_prod_early_stop_min_frames"])),
                            effective_traj_frames,
                        )
                    )
                ),
                "--prod-early-stop-window",
                str(int(traj_stage2_settings["traj_prod_early_stop_window"])),
                "--prod-early-stop-contact-drift",
                str(float(traj_stage2_settings["traj_prod_early_stop_contact_drift"])),
                "--prod-early-stop-min-distance-drift-A",
                str(float(traj_stage2_settings["traj_prod_early_stop_min_distance_drift_A"])),
                "--prod-early-stop-max-mean-min-distance-A",
                str(float(traj_stage2_settings["traj_prod_early_stop_max_mean_min_distance_A"])),
            ]
        )
    if bool(getattr(args, "traj_prod_light_artifacts", True)):
        out.extend(
            [
                "--prod-light-artifacts",
                "--prod-light-progress-every-jobs",
                str(int(max(1, int(getattr(args, "traj_prod_light_progress_every_jobs", 250))))),
            ]
        )
    return out


def _build_sla_summary(
    *,
    out_prefix: str,
    stage0: Dict[str, Any],
    stage1: Dict[str, Any],
    stage2_traj: Optional[Dict[str, Any]],
    stage2_meta: Dict[str, Any],
    stage3: Dict[str, Any],
    stage3b: Dict[str, Any],
    stage4: Dict[str, Any],
    stage45: Dict[str, Any],
    stage5: Dict[str, Any],
    gate_summary: Dict[str, Any],
    queue_csv: str,
    trajectory_root: str,
    heavy_enabled: bool,
    traj_prod: Optional[Dict[str, Any]] = None,
    traj_stage2_settings: Optional[Dict[str, Any]] = None,
    traj_stage2_diag: Optional[Dict[str, Any]] = None,
    traj_stage2_summary_json: str = "",
    physics_refinement: Optional[Dict[str, Any]] = None,
    physics_refinement_summary_json: str = "",
) -> Dict[str, Any]:
    durations = {
        "stage0_leakage_audit_sec": _duration_of(stage0),
        "stage1_mapping_sec": _duration_of(stage1),
        "stage2_trajectory_sec": _duration_of(stage2_traj),
        "stage2_residual_meta_sec": _duration_of(stage2_meta),
        "stage3_backmapping_scoring_sec": _duration_of(stage3),
        "stage3b_physics_refinement_sec": _duration_of(stage3b),
        "stage4_calibration_sec": _duration_of(stage4),
        "stage45_integrity_sec": _duration_of(stage45),
        "stage5_ranking_sec": _duration_of(stage5),
    }
    total_dur = float(sum(float(v) for v in durations.values()))
    queue_rows = _csv_rows_minus_header(queue_csv)
    stage2_dur = float(durations.get("stage2_trajectory_sec", 0.0))
    stage3_dur = float(durations.get("stage3_backmapping_scoring_sec", 0.0))
    stage3b_dur = float(durations.get("stage3b_physics_refinement_sec", 0.0))
    queue_rate_stage2 = float(queue_rows / stage2_dur) if (queue_rows > 0 and stage2_dur > 0) else None
    queue_rate_stage3 = float(queue_rows / stage3_dur) if (queue_rows > 0 and stage3_dur > 0) else None
    queue_rate_stage3b = float(queue_rows / stage3b_dur) if (queue_rows > 0 and stage3b_dur > 0) else None
    gate_failed = gate_summary.get("failed_metrics", []) if isinstance(gate_summary, dict) else []
    gate_failed_n = int(len(gate_failed) if isinstance(gate_failed, list) else 0)
    gate_total_n = int(max(1, 1 + gate_failed_n))
    failure_rate = float(gate_failed_n / gate_total_n)
    out = {
        "pass": bool(gate_summary.get("pass", False)),
        "out_prefix": str(out_prefix),
        "queue_rows": int(queue_rows),
        "trajectory_root": str(trajectory_root),
        "heavy_artifacts_enabled": bool(heavy_enabled),
        "durations_sec": durations,
        "total_latency_sec": total_dur,
        "p95_latency_proxy_sec": float(max(durations.values()) if durations else 0.0),
        "queue_rate_stage2_rows_per_sec": queue_rate_stage2,
        "queue_rate_stage3_rows_per_sec": queue_rate_stage3,
        "queue_rate_stage3b_rows_per_sec": queue_rate_stage3b,
        "gate_failed_metric_count": gate_failed_n,
        "gate_failure_rate_proxy": failure_rate,
    }
    if isinstance(traj_prod, dict):
        out["traj_prod"] = dict(traj_prod)
    if isinstance(physics_refinement, dict):
        out["physics_refinement"] = dict(physics_refinement)
    if isinstance(traj_prod, dict) or isinstance(traj_stage2_settings, dict) or isinstance(traj_stage2_diag, dict):
        op = _traj_prod_operational_summary(
            traj_prod=traj_prod,
            traj_stage2_settings=traj_stage2_settings,
            traj_stage2_diag=traj_stage2_diag,
        )
        out["traj_prod_operational_summary"] = op
        out["traj_prod_requested_preset"] = op.get("requested_preset")
        out["traj_prod_resolved_preset"] = op.get("resolved_preset")
        out["traj_prod_strict_enabled"] = op.get("strict_enabled")
        out["traj_prod_strict_status"] = op.get("strict_status")
        out["traj_prod_light_artifacts"] = op.get("light_artifacts")
        out["traj_prod_effective_writer_workers"] = op.get("effective_writer_workers")
        out["traj_prod_effective_writer_max_pending"] = op.get("effective_writer_max_pending")
    stage2_engine = _traj_stage2_engine_telemetry(traj_stage2_summary_json)
    if stage2_engine:
        out["traj_stage2_engine_summary"] = stage2_engine
        out["traj_stage2_summary_json_present"] = bool(stage2_engine.get("summary_json_present", False))
        out["traj_stage2_engine_prod_mode"] = stage2_engine.get("prod_mode")
        out["traj_stage2_engine_prod_light_artifacts"] = stage2_engine.get("prod_light_artifacts")
        out["traj_stage2_engine_prod_frame_budget_applied_count"] = stage2_engine.get("prod_frame_budget_applied_count")
        out["traj_stage2_engine_prod_early_stop_batch_count"] = stage2_engine.get("prod_early_stop_batch_count")
        out["traj_stage2_engine_prod_early_stop_row_count"] = stage2_engine.get("prod_early_stop_row_count")
        out["traj_stage2_engine_mean_sim_frames_count"] = stage2_engine.get("mean_sim_frames_count")
        out["traj_stage2_engine_mean_frames_effective_cap"] = stage2_engine.get("mean_frames_effective_cap")
        out["traj_stage2_engine_job_batch_derate_count"] = stage2_engine.get("job_batch_derate_count")
        out["traj_stage2_engine_target_tail_csv_present"] = stage2_engine.get("target_tail_csv_present")
        out["traj_stage2_engine_manifest_chunks_dir_present"] = stage2_engine.get("manifest_chunks_dir_present")
        out["traj_stage2_engine_summary_md_present"] = stage2_engine.get("summary_md_present")
    refinement_telemetry = _physics_refinement_telemetry(physics_refinement_summary_json)
    if refinement_telemetry:
        out["physics_refinement_summary"] = refinement_telemetry
        out["physics_refinement_summary_json_present"] = bool(refinement_telemetry.get("summary_json_present", False))
        out["physics_refinement_enabled"] = refinement_telemetry.get("enabled")
        out["physics_refinement_mode"] = refinement_telemetry.get("mode")
        out["physics_refinement_backend"] = refinement_telemetry.get("backend")
        out["physics_refinement_selected_count"] = refinement_telemetry.get("selected_count")
        out["physics_refinement_selected_fraction"] = refinement_telemetry.get("selected_fraction")
        out["physics_refinement_shortlist_csv_present"] = refinement_telemetry.get("shortlist_csv_present")
        out["physics_refinement_summary_md_present"] = refinement_telemetry.get("summary_md_present")
    return out


def _read_service_error_profile(path: str) -> Dict[str, Any]:
    prof = _read_json_if_exists(path)
    if not prof:
        return {}
    if not isinstance(prof.get("map"), dict):
        prof["map"] = {}
    if not isinstance(prof.get("retryable_stages"), list):
        prof["retryable_stages"] = []
    return prof


def _looks_like_path(s: str) -> bool:
    v = str(s or "").strip()
    if not v:
        return False
    low = v.lower()
    if low.startswith(("http://", "https://", "s3://")):
        return False
    if ("/" in v) or ("\\" in v) or v.startswith(".") or v.startswith("~"):
        return True
    return any(
        low.endswith(ext)
        for ext in (
            ".json",
            ".csv",
            ".md",
            ".txt",
            ".log",
            ".pdb",
            ".sdf",
            ".mol2",
            ".zip",
            ".tar",
            ".tar.gz",
            ".npy",
            ".npz",
        )
    )


def _parse_gate_override_row_key(row_key: str) -> tuple[str, str]:
    text = str(row_key or "").strip()
    if "::" not in text:
        return "", ""
    target, ligand_id = text.split("::", 1)
    return str(target).strip(), str(ligand_id).strip()


def _load_gate_distance_override_rows(
    override_csv: str,
    *,
    join_target: str = "target",
    join_ligand: str = "ligand_id",
) -> Dict[str, Any]:
    report: Dict[str, Any] = {
        "requested": bool(str(override_csv or "").strip()),
        "path": str(override_csv or "").strip(),
        "present": False,
        "row_count": 0,
        "valid_row_count": 0,
        "rows": [],
        "warnings": [],
    }
    src = str(override_csv or "").strip()
    if not src:
        return report
    if not os.path.exists(src):
        report["warnings"].append(f"gate distance override csv missing: {src}")
        return report
    try:
        df = pd.read_csv(src)
    except Exception as e:
        report["warnings"].append(f"gate distance override csv unreadable: {src} ({e})")
        return report
    report["present"] = True
    report["row_count"] = int(len(df))
    value_candidates = (
        "override_mean_min_distance_A",
        "rescored_mean_min_distance_A",
        "realized_mean_min_distance_A",
        "projected_mean_min_distance_A",
        "mean_min_distance_A",
    )
    rows: List[Dict[str, Any]] = []
    for raw in df.to_dict(orient="records"):
        row = dict(raw or {})
        target = str(row.get(join_target, "") or row.get("target", "")).strip()
        ligand_id = str(row.get(join_ligand, "") or row.get("ligand_id", "")).strip()
        if (not target) or (not ligand_id):
            parsed_target, parsed_ligand = _parse_gate_override_row_key(str(row.get("row_key", "")))
            target = target or parsed_target
            ligand_id = ligand_id or parsed_ligand
        override_value = None
        for col in value_candidates:
            if col not in row or row.get(col) in {"", None}:
                continue
            try:
                value = float(row.get(col))
            except Exception:
                value = None
            if value is not None and math.isfinite(float(value)):
                override_value = float(value)
                break
        if (not target) or (not ligand_id) or (override_value is None):
            report["warnings"].append(
                f"ignored invalid gate override row: target={target or '-'} ligand_id={ligand_id or '-'}"
            )
            continue
        rows.append(
            {
                "target": target,
                "ligand_id": ligand_id,
                "override_mean_min_distance_A": float(override_value),
                "row_key": str(row.get("row_key", "")).strip() or f"{target}::{ligand_id}",
                "canonical_retry_preset_id": str(row.get("canonical_retry_preset_id", "")).strip(),
                "source_packet_artifact": str(row.get("source_packet_artifact", "")).strip(),
            }
        )
    report["valid_row_count"] = int(len(rows))
    report["rows"] = rows
    return report


def _apply_gate_distance_overrides(
    unique_df: pd.DataFrame,
    override_report: Dict[str, Any],
    *,
    join_target: str = "target",
    join_ligand: str = "ligand_id",
) -> tuple[pd.DataFrame, Dict[str, Any]]:
    out_df = unique_df.copy()
    stats: Dict[str, Any] = {
        "requested": bool((override_report or {}).get("requested", False)),
        "present": bool((override_report or {}).get("present", False)),
        "path": str((override_report or {}).get("path", "") or ""),
        "row_count": int((override_report or {}).get("row_count", 0) or 0),
        "valid_row_count": int((override_report or {}).get("valid_row_count", 0) or 0),
        "applied_count": 0,
        "missing_count": 0,
        "missing_row_keys": [],
        "warnings": list((override_report or {}).get("warnings", []) or []),
    }
    rows = list((override_report or {}).get("rows", []) or [])
    if out_df.empty or (not rows) or ("mean_min_distance_A" not in out_df.columns):
        return out_df, stats
    row_keys = out_df[join_target].astype(str).str.strip() + "::" + out_df[join_ligand].astype(str).str.strip()
    row_to_index = {str(key): idx for idx, key in row_keys.items()}
    for row in rows:
        key = f"{str(row.get('target', '')).strip()}::{str(row.get('ligand_id', '')).strip()}"
        idx = row_to_index.get(key)
        if idx is None:
            stats["missing_count"] += 1
            stats["missing_row_keys"].append(key)
            continue
        out_df.at[idx, "mean_min_distance_A"] = float(row.get("override_mean_min_distance_A"))
        stats["applied_count"] += 1
    return out_df, stats


def _to_abs_path(s: str) -> str:
    v = str(s or "").strip()
    if not v:
        return ""
    try:
        return os.path.abspath(os.path.expanduser(v))
    except Exception:
        return v


def _attach_absolute_paths(out_prefix: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(payload) if isinstance(payload, dict) else {}
    artifacts = out.get("artifacts", {})
    artifacts_abs: Dict[str, str] = {}
    if isinstance(artifacts, dict):
        for k, v in artifacts.items():
            if isinstance(v, str) and _looks_like_path(v):
                ap = _to_abs_path(v)
                if ap:
                    artifacts_abs[str(k)] = ap
    summary_json_abs = _to_abs_path(f"{out_prefix}_summary.json")
    summary_md_abs = _to_abs_path(f"{out_prefix}_summary.md")
    if summary_json_abs:
        artifacts_abs.setdefault("summary_json", summary_json_abs)
    if summary_md_abs:
        artifacts_abs.setdefault("summary_md", summary_md_abs)
    out["artifacts_abs"] = artifacts_abs
    out["path_info"] = {
        "cwd": _to_abs_path("."),
        "out_prefix_abs": _to_abs_path(out_prefix),
        "summary_json_abs": summary_json_abs,
        "summary_md_abs": summary_md_abs,
    }
    return out


def _attach_service_result(payload: Dict[str, Any], args: argparse.Namespace) -> Dict[str, Any]:
    out = dict(payload) if isinstance(payload, dict) else {}
    failed_stage = str(out.get("failed_stage", "") or "").strip()
    passed = bool(out.get("pass", False))
    prof = _read_service_error_profile(str(args.service_error_codes_json))
    code_map = prof.get("map", {}) if isinstance(prof.get("map"), dict) else {}
    ok_code = str(prof.get("ok_code", "HTVS_OK"))
    unknown_code = str(prof.get("unknown_error_code", "HTVS_UNKNOWN_ERROR"))
    error_code = ok_code if passed else str(code_map.get(failed_stage, unknown_code))
    retryable_stages = {
        str(x).strip() for x in (prof.get("retryable_stages", []) if isinstance(prof.get("retryable_stages"), list) else [])
    }
    retryable = (not passed) and (failed_stage in retryable_stages)
    retry_after = (
        int(args.service_retry_after_sec_transient)
        if retryable
        else int(args.service_retry_after_sec_default)
    )
    out["schema_version"] = str(args.service_schema_version)
    out["service_result"] = {
        "status": "ok" if passed else "error",
        "error_code": error_code,
        "failed_stage": failed_stage if failed_stage else None,
        "retryable": bool(retryable),
        "retry_after_sec": int(max(retry_after, 0)),
    }
    out["service_contract"] = {
        "data_contract_json": str(args.data_contract_json),
        "service_error_codes_json": str(args.service_error_codes_json),
    }
    return out


def _finalize_and_write(out_prefix: str, payload: Dict[str, Any], args: argparse.Namespace) -> Dict[str, Any]:
    out = _attach_service_result(payload, args)
    out = _attach_absolute_paths(out_prefix, out)
    summary_json = f"{out_prefix}_summary.json"
    with open(summary_json, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    # Keep CLOSEOUT_LATEST in sync at each run finalization for external review handoff.
    if callable(_write_closeout_latest):
        try:
            _write_closeout_latest(
                summary_json=str(summary_json),
                out_dir="runs",
                prefix="CLOSEOUT",
                symlink_latest=True,
            )
        except Exception:
            pass
    return out


def _stage1_eval_positive_check(
    *,
    queue_csv: str,
    labels_csv: str,
    split_csv: str,
    eval_roles: List[str],
    target_col: str,
    ligand_col: str,
    role_col: str,
    binder_col: str,
    require_3d_ready: bool = True,
    require_native_path_exists: bool = True,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "ok": False,
        "queue_csv": str(queue_csv),
        "labels_csv": str(labels_csv),
        "split_csv": str(split_csv),
        "eval_roles": list(eval_roles),
        "rows_queue_keys": 0,
        "rows_eval_positive_total": 0,
        "rows_eval_positive_in_queue": 0,
        "rows_eval_positive_3d_ready": 0,
        "missing_eval_positive_count": 0,
        "not_ready_eval_positive_count": 0,
        "missing_examples": [],
        "not_ready_examples": [],
        "error": "",
    }
    try:
        if (not os.path.exists(queue_csv)) or (not os.path.exists(labels_csv)) or (not os.path.exists(split_csv)):
            out["error"] = "required csv missing"
            return out
        q = pd.read_csv(queue_csv)
        l = pd.read_csv(labels_csv)
        s = pd.read_csv(split_csv)
        for df_name, df in [("queue", q), ("labels", l), ("split", s)]:
            for c in [target_col, ligand_col]:
                if c not in df.columns:
                    out["error"] = f"{df_name} missing key column: {c}"
                    return out
        if role_col not in s.columns:
            out["error"] = f"split missing role column: {role_col}"
            return out
        if binder_col not in l.columns:
            out["error"] = f"labels missing binder column: {binder_col}"
            return out

        qk = q[[target_col, ligand_col]].drop_duplicates().reset_index(drop=True)
        out["rows_queue_keys"] = int(len(qk))
        ss = s[s[role_col].astype(str).isin(eval_roles)].copy() if eval_roles else s.copy()
        eval_keys = ss[[target_col, ligand_col]].drop_duplicates().reset_index(drop=True)
        lp = l[l[binder_col].astype(int) == 1][[target_col, ligand_col]].drop_duplicates().reset_index(drop=True)
        eval_pos = eval_keys.merge(lp, on=[target_col, ligand_col], how="inner")
        out["rows_eval_positive_total"] = int(len(eval_pos))
        in_q = eval_pos.merge(qk, on=[target_col, ligand_col], how="inner")
        out["rows_eval_positive_in_queue"] = int(len(in_q))

        q_ready = q.copy()
        if "ligand_bead_count" in q_ready.columns:
            try:
                q_ready["_ready_bead_count"] = pd.to_numeric(q_ready["ligand_bead_count"], errors="coerce").fillna(0.0) >= 1.0
            except Exception:
                q_ready["_ready_bead_count"] = False
        else:
            q_ready["_ready_bead_count"] = False
        coord_cols = [c for c in ["ligand_bead0_x", "ligand_bead0_y", "ligand_bead0_z"] if c in q_ready.columns]
        if len(coord_cols) == 3:
            try:
                cc = q_ready[coord_cols].apply(pd.to_numeric, errors="coerce")
                q_ready["_ready_coords"] = cc.notna().all(axis=1)
            except Exception:
                q_ready["_ready_coords"] = False
        else:
            q_ready["_ready_coords"] = False
        if require_native_path_exists and ("native_pdb_path" in q_ready.columns):
            q_ready["_ready_native"] = q_ready["native_pdb_path"].astype(str).apply(
                lambda p: bool(str(p).strip()) and os.path.exists(str(p).strip())
            )
        elif require_native_path_exists:
            q_ready["_ready_native"] = False
        else:
            q_ready["_ready_native"] = True
        q_ready["_ready_3d"] = q_ready["_ready_bead_count"] & q_ready["_ready_coords"] & q_ready["_ready_native"]

        if bool(require_3d_ready):
            # Deduplicate at key-level before readiness join: queue may contain
            # multiple rows per (target, ligand_id), and a raw merge would inflate
            # the ready count and weaken the gate.
            q_ready_key = (
                q_ready[[target_col, ligand_col, "_ready_3d"]]
                .groupby([target_col, ligand_col], as_index=False)
                .agg({"_ready_3d": "max"})
            )
            in_q_ready = eval_pos.merge(
                q_ready_key,
                on=[target_col, ligand_col],
                how="left",
            )
            in_q_ready["_ready_3d"] = in_q_ready["_ready_3d"].fillna(False).astype(bool)
            out["rows_eval_positive_3d_ready"] = int(in_q_ready["_ready_3d"].sum())
            bad = in_q_ready[in_q_ready["_ready_3d"] == False][[target_col, ligand_col]].drop_duplicates().reset_index(drop=True)
            out["not_ready_eval_positive_count"] = int(len(bad))
            if len(bad) > 0:
                out["not_ready_examples"] = bad.head(10).to_dict(orient="records")
        else:
            out["rows_eval_positive_3d_ready"] = int(out["rows_eval_positive_in_queue"])
            out["not_ready_eval_positive_count"] = 0

        miss = eval_pos.merge(qk, on=[target_col, ligand_col], how="left", indicator=True)
        miss = miss[miss["_merge"] == "left_only"][[target_col, ligand_col]].reset_index(drop=True)
        out["missing_eval_positive_count"] = int(len(miss))
        if len(miss) > 0:
            out["missing_examples"] = miss.head(10).to_dict(orient="records")
        out["ok"] = True
        return out
    except Exception as e:
        out["error"] = str(e)
    return out


def _merge_roles_csv(*role_specs: str) -> str:
    out: List[str] = []
    seen = set()
    for spec in role_specs:
        for tok in [x.strip() for x in str(spec or "").split(",") if x.strip()]:
            if tok in seen:
                continue
            seen.add(tok)
            out.append(tok)
    return ",".join(out)


def _clone_gate_summary(template: Dict[str, Any], enabled: bool) -> Dict[str, Any]:
    out = dict(template) if isinstance(template, dict) else {}
    out["enabled"] = bool(enabled)
    out["pass"] = True
    out["failed_metrics"] = []
    out["warnings"] = list(template.get("warnings", [])) if isinstance(template, dict) else []
    return out


def _strict_gate_from_operational(op_gate: Dict[str, Any], args: argparse.Namespace) -> Dict[str, Any]:
    strict_gate = _clone_gate_summary(op_gate, enabled=bool(getattr(args, "enforce_strict_gate", False)))
    if not bool(strict_gate.get("enabled", False)):
        strict_gate["pass"] = True
        return strict_gate

    def _num(v: Any) -> Optional[float]:
        if isinstance(v, (int, float)):
            return float(v)
        return None

    checks_min = [
        ("min_trajectory_frames", _num(op_gate.get("min_frames_observed")), float(args.strict_gate_min_frames)),
        ("ranking_unique_auc", _num(op_gate.get("ranking_unique_auc")), float(args.strict_gate_ranking_unique_auc_min)),
        ("ranking_ood_unique_auc", _num(op_gate.get("ranking_ood_unique_auc")), float(args.strict_gate_ranking_ood_auc_min)),
        ("ranking_pr_auc", _num(op_gate.get("ranking_pr_auc")), float(args.strict_gate_pr_auc_min)),
        ("ranking_ef1", _num(op_gate.get("ranking_ef1")), float(args.strict_gate_ef1_min)),
        ("ranking_bedroc", _num(op_gate.get("ranking_bedroc")), float(args.strict_gate_bedroc_min)),
        ("ranking_roc_auc_ci_low", _num(op_gate.get("ranking_roc_auc_ci_low")), float(args.strict_gate_roc_auc_ci_lower_min)),
        ("ranking_pr_auc_ci_low", _num(op_gate.get("ranking_pr_auc_ci_low")), float(args.strict_gate_pr_auc_ci_lower_min)),
        ("ranking_ef1_ci_low", _num(op_gate.get("ranking_ef1_ci_low")), float(args.strict_gate_ef1_ci_lower_min)),
        ("topk_hit_rate", _num(op_gate.get("ranking_topk_hit_rate")), float(args.strict_gate_topk_hit_rate_min)),
        (
            "ranking_expected_score_coverage_ratio",
            _num(op_gate.get("ranking_expected_score_coverage_ratio")),
            float(args.strict_gate_ranking_min_expected_score_coverage),
        ),
        (
            "ranking_score_unique_ratio",
            _num(op_gate.get("ranking_score_unique_ratio")),
            float(args.strict_gate_score_unique_ratio_min),
        ),
    ]
    for metric, value, threshold in checks_min:
        if threshold <= 0:
            continue
        if value is None:
            strict_gate["failed_metrics"].append({"metric": metric, "value": value, "threshold": threshold})
            continue
        if float(value) < float(threshold):
            strict_gate["failed_metrics"].append({"metric": metric, "value": float(value), "threshold": float(threshold)})

    checks_max = [
        ("mean_min_distance_A", _num(op_gate.get("mean_min_distance_A")), float(args.strict_gate_max_mean_min_distance_A)),
        ("ranking_brier", _num(op_gate.get("ranking_brier")), float(args.strict_gate_brier_max)),
        ("ranking_ece", _num(op_gate.get("ranking_ece")), float(args.strict_gate_ece_max)),
        ("ranking_score_tie_ratio", _num(op_gate.get("ranking_score_tie_ratio")), float(args.strict_gate_score_tie_ratio_max)),
        ("ranking_score_mode_ratio", _num(op_gate.get("ranking_score_mode_ratio")), float(args.strict_gate_score_mode_ratio_max)),
    ]
    for metric, value, threshold in checks_max:
        if threshold <= 0:
            continue
        if value is None:
            strict_gate["failed_metrics"].append({"metric": metric, "value": value, "threshold": threshold})
            continue
        if float(value) > float(threshold):
            strict_gate["failed_metrics"].append({"metric": metric, "value": float(value), "threshold": float(threshold)})

    pos_count = _num(op_gate.get("ranking_positive_count"))
    if int(args.strict_gate_min_positive_count) > 0:
        if (pos_count is None) or (int(pos_count) < int(args.strict_gate_min_positive_count)):
            strict_gate["failed_metrics"].append(
                {
                    "metric": "ranking_positive_count",
                    "value": None if pos_count is None else int(pos_count),
                    "threshold": int(args.strict_gate_min_positive_count),
                }
            )
    pos_ood = _num(op_gate.get("ranking_ood_positive_count"))
    if int(args.strict_gate_min_ood_positive_count) > 0:
        if (pos_ood is None) or (int(pos_ood) < int(args.strict_gate_min_ood_positive_count)):
            strict_gate["failed_metrics"].append(
                {
                    "metric": "ranking_ood_positive_count",
                    "value": None if pos_ood is None else int(pos_ood),
                    "threshold": int(args.strict_gate_min_ood_positive_count),
                }
            )

    if bool(args.strict_gate_fail_on_orientation_suspect) and bool(op_gate.get("ranking_score_orientation_suspect", False)):
        strict_gate["failed_metrics"].append(
            {
                "metric": "ranking_score_orientation_suspect",
                "value": bool(op_gate.get("ranking_score_orientation_suspect", False)),
                "threshold": False,
            }
        )

    strict_gate["pass"] = len(strict_gate["failed_metrics"]) == 0
    return strict_gate


def run_pipeline(args: argparse.Namespace) -> Dict[str, Any]:
    date_tag = str(args.date_tag).strip() or dt.date.today().isoformat()
    out_prefix = str(args.out_prefix).strip() or f"runs/ligand_htvs_pipeline_{date_tag}"
    _ensure_parent(f"{out_prefix}_summary.json")
    resume_stage3_only = bool(getattr(args, "resume_stage3_only", False))
    stage_lock = {
        "enabled": bool(getattr(args, "single_instance", True)),
        "ok": True,
        "lock_path": "",
        "owner": "",
    }
    lock_handle: Dict[str, Any] = {"fd": None}
    if bool(stage_lock["enabled"]):
        lock_path = str(getattr(args, "lock_file", "")).strip() or f"{out_prefix}.lock"
        lock_handle = _acquire_instance_lock(lock_path)
        stage_lock.update(
            {
                "ok": bool(lock_handle.get("ok", False)),
                "lock_path": str(lock_handle.get("lock_path", "")),
                "owner": str(lock_handle.get("owner", "")),
            }
        )
        if not bool(lock_handle.get("ok", False)):
            payload = {
                "pass": False,
                "failed_stage": "stage_lock",
                "run_scope": str(args.run_scope),
                "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
                "stages": {"stage_lock": stage_lock},
                "artifacts": {"summary_json": f"{out_prefix}_summary.json"},
            }
            return _finalize_and_write(out_prefix, payload, args)
        atexit.register(_release_instance_lock, lock_handle)

    mode = str(args.run_scope).strip().lower()
    if mode == "smoke_then_full":
        smoke_args = argparse.Namespace(**vars(args))
        smoke_args.run_scope = "smoke"
        smoke_args.out_prefix = f"{out_prefix}_smoke"
        smoke_payload = run_pipeline(smoke_args)
        full_payload: Dict[str, Any] = {}
        if bool(smoke_payload.get("pass", False)):
            full_args = argparse.Namespace(**vars(args))
            full_args.run_scope = "full"
            full_args.out_prefix = f"{out_prefix}_full"
            full_payload = run_pipeline(full_args)
        final_pass = bool(smoke_payload.get("pass", False)) and bool(full_payload.get("pass", False))
        failed_stage = None
        if not bool(smoke_payload.get("pass", False)):
            failed_stage = "smoke"
        elif not bool(full_payload.get("pass", False)):
            failed_stage = "full"
        payload = {
            "pass": bool(final_pass),
            "failed_stage": failed_stage,
            "run_scope": "smoke_then_full",
            "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
            "stages": {
                "stage_lock": stage_lock,
                "smoke": smoke_payload,
                "full": full_payload,
            },
            "artifacts": {
                "summary_json": f"{out_prefix}_summary.json",
                "summary_md": f"{out_prefix}_summary.md",
                "smoke_summary_json": str(smoke_payload.get("artifacts", {}).get("summary_json", "")),
                "full_summary_json": str(full_payload.get("artifacts", {}).get("summary_json", "")),
            },
        }
        payload = _finalize_and_write(out_prefix, payload, args)
        lines = [
            "# Ligand HTVS Pipeline (Smoke -> Full)",
            "",
            f"- generated_at_local: {payload['generated_at_local']}",
            f"- pass: {payload['pass']}",
            f"- failed_stage: {payload['failed_stage']}",
            f"- smoke_pass: {bool(smoke_payload.get('pass', False))}",
            f"- full_pass: {bool(full_payload.get('pass', False))}",
            f"- smoke_summary_json: `{payload['artifacts']['smoke_summary_json']}`",
            f"- full_summary_json: `{payload['artifacts']['full_summary_json']}`",
            f"- summary_json_abs: `{payload.get('path_info', {}).get('summary_json_abs', '')}`",
        ]
        with open(f"{out_prefix}_summary.md", "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        return payload
    if mode not in {"smoke", "full"}:
        raise ValueError("--run-scope must be smoke|full|smoke_then_full")

    contract_input = {"ok": True, "skipped": True, "errors": [], "warnings": []}
    if bool(args.enforce_data_contract):
        contract_input = _validate_data_contract_input(args)
        contract_input["skipped"] = False
        if not bool(contract_input.get("ok", False)):
            payload = {
                "pass": False,
                "failed_stage": "stage_contract_input",
                "stages": {
                    "stage_lock": stage_lock,
                    "stage_contract_input": contract_input,
                },
                "artifacts": {"summary_json": f"{out_prefix}_summary.json"},
            }
            return _finalize_and_write(out_prefix, payload, args)

    heavy_paths = _resolve_heavy_artifact_paths(
        out_prefix=out_prefix,
        heavy_root=str(args.heavy_artifacts_root),
        subdir=str(args.heavy_artifacts_subdir),
        auto_mount=bool(args.auto_heavy_artifacts_root),
    )
    if bool(args.heavy_artifacts_root) and (not bool(heavy_paths.get("enabled", False))):
        payload = {
            "pass": False,
            "failed_stage": "stage_heavy_artifacts_root",
            "stages": {
                "stage_lock": stage_lock,
                "stage_contract_input": contract_input,
                "stage_heavy_artifacts_root": heavy_paths,
            },
            "artifacts": {"summary_json": f"{out_prefix}_summary.json"},
        }
        return _finalize_and_write(out_prefix, payload, args)

    replicas = int(args.replicas_smoke if mode == "smoke" else args.replicas_full)
    max_ligands = int(args.max_ligands_smoke if mode == "smoke" else args.max_ligands_full)
    jobs_per_target = int(args.jobs_per_target_smoke if mode == "smoke" else args.jobs_per_target_full)
    max_jobs_score = int(args.max_jobs_score_smoke if mode == "smoke" else args.max_jobs_score_full)
    traj_stage2_diag = _traj_prod_stage2_preset_diagnostics(args)
    traj_prod_summary = _traj_prod_runtime_summary(args, traj_stage2_diag)
    traj_stage2_settings = _traj_stage2_runtime_settings(args, mode=mode)
    traj_frames = int(traj_stage2_settings["traj_frames"])

    rec0: Dict[str, Any] = {"ok": True, "skipped": True, "cmd": [], "cmd_str": ""}
    if (not resume_stage3_only) and bool(args.run_leakage_audit):
        stage0_prefix = f"{out_prefix}_stage0_leakage"
        audit_eval_roles = str(args.leakage_eval_roles).strip()
        if not audit_eval_roles:
            audit_eval_roles = f"{str(args.ranking_eval_roles)},{str(args.ranking_ood_eval_roles)}"
        stage0_cmd = [
            sys.executable,
            "tools/audit_ligand_leakage.py",
            "--split-csv",
            str(args.eval_split_csv),
            "--fit-roles",
            str(args.leakage_fit_roles or args.calibration_fit_roles),
            "--eval-roles",
            str(audit_eval_roles),
            "--target-meta-csv",
            str(args.leakage_target_meta_csv),
            "--ligand-meta-csv",
            str(args.leakage_ligand_meta_csv),
            "--max-key-overlap",
            str(int(args.leakage_max_key_overlap)),
            "--max-target-overlap",
            str(int(args.leakage_max_target_overlap)),
            "--max-family-overlap-ratio",
            str(float(args.leakage_max_family_overlap_ratio)),
            "--max-scaffold-overlap-ratio",
            str(float(args.leakage_max_scaffold_overlap_ratio)),
            "--max-allowed-seq-identity",
            str(float(args.leakage_max_allowed_seq_identity)),
            "--max-allowed-pocket-jaccard",
            str(float(args.leakage_max_allowed_pocket_jaccard)),
            "--out-json",
            f"{stage0_prefix}_summary.json",
            "--out-csv",
            f"{stage0_prefix}_summary.csv",
            "--out-md",
            f"{stage0_prefix}_summary.md",
        ]
        rec0 = _run_cmd(stage0_cmd)
        if not rec0["ok"]:
            payload = {
                "pass": False,
                "failed_stage": "stage0_leakage_audit",
                "stages": {"stage_lock": stage_lock, "stage0_leakage_audit": rec0},
                "artifacts": {"summary_json": f"{out_prefix}_summary.json"},
            }
            return _finalize_and_write(out_prefix, payload, args)

    stage1_prefix = f"{out_prefix}_stage1"
    queue_csv = f"{stage1_prefix}_queue.csv"
    ligand_json = f"{stage1_prefix}_ligands.json"
    stage1_summary = f"{stage1_prefix}_summary.json"
    stage1_md = f"{stage1_prefix}_summary.md"

    stage1_positive_check: Dict[str, Any] = {"ok": True, "skipped": True}
    rec1: Dict[str, Any]
    stage1_roles: List[str] = []
    for src in [str(args.calibration_fit_roles), str(args.ranking_eval_roles), str(args.ranking_ood_eval_roles)]:
        for tok in [x.strip() for x in str(src).split(",") if x.strip()]:
            if tok not in stage1_roles:
                stage1_roles.append(tok)
    stage1_roles_csv = ",".join(stage1_roles)
    reuse_stage1 = bool(args.reuse_stage1_if_exists)
    if resume_stage3_only:
        if not os.path.exists(queue_csv):
            payload = {
                "pass": False,
                "failed_stage": "stage1_ligand_mapping",
                "stages": {
                    "stage_lock": stage_lock,
                    "stage0_leakage_audit": rec0,
                    "stage1_ligand_mapping": {
                        "ok": False,
                        "skipped": True,
                        "reused": False,
                        "stderr_tail": f"resume-stage3-only requested but missing queue: {queue_csv}",
                    },
                },
                "artifacts": {"summary_json": f"{out_prefix}_summary.json"},
            }
            return _finalize_and_write(out_prefix, payload, args)
        rec1 = {
            "ok": True,
            "skipped": True,
            "reused": True,
            "resume_stage3_only": True,
            "queue_csv": queue_csv,
            "ligand_json": ligand_json if os.path.exists(ligand_json) else "",
            "stage1_summary_json": stage1_summary if os.path.exists(stage1_summary) else "",
            "cmd": [],
            "cmd_str": "",
        }
    elif reuse_stage1 and os.path.exists(queue_csv) and os.path.exists(ligand_json):
        stage1_obj = _read_json_if_exists(stage1_summary)
        queue_rows = int(float(stage1_obj.get("queue_rows", 0) or 0))
        if queue_rows <= 0:
            queue_rows = _csv_rows_minus_header(queue_csv)
        rec1 = {
            "cmd": [],
            "cmd_str": "",
            "ok": bool(queue_rows > 0),
            "returncode": 0 if queue_rows > 0 else 1,
            "stdout_tail": "",
            "stderr_tail": "" if queue_rows > 0 else "stage1 reuse requested but queue rows <= 0",
            "skipped": True,
            "reused": True,
            "queue_rows": int(queue_rows),
            "queue_csv": queue_csv,
            "ligand_json": ligand_json,
            "stage1_summary_json": stage1_summary,
        }
    else:
        stage1_cmd = [
            sys.executable,
            "tools/build_ligand_mapping_queue.py",
            "--targets",
            str(args.targets),
            "--ligand-sdf",
            str(args.ligand_sdf),
            "--ligand-csv",
            str(args.ligand_csv),
            "--max-ligands",
            str(max_ligands),
            "--replicas",
            str(replicas),
            "--jobs-per-target",
            str(jobs_per_target),
            "--queue-policy",
            str(args.queue_policy),
            "--csv-prioritize-binders"
            if bool(args.stage1_csv_prioritize_binders)
            else "--no-csv-prioritize-binders",
            "--csv-binder-col",
            str(args.stage1_csv_binder_col),
            "--csv-relax-3d"
            if bool(args.csv_relax_3d)
            else "--no-csv-relax-3d",
            "--csv-relax-max-iters",
            str(int(args.csv_relax_max_iters)),
            "--csv-relax-embed-seed",
            str(int(args.csv_relax_embed_seed)),
            "--csv-relax-workers",
            str(int(args.csv_relax_workers)),
            "--csv-smiles-cache-json",
            str(args.csv_smiles_cache_json),
            "--target-pocket-csv",
            str(args.target_pocket_csv),
            "--target-native-csv",
            str(args.target_native_csv),
            "--target-ligand-csv",
            str(args.eval_split_csv),
            "--target-ligand-roles",
            str(stage1_roles_csv),
            "--target-ligand-role-col",
            "role",
            "--target-ligand-target-col",
            "target",
            "--target-ligand-id-col",
            "ligand_id",
            "--out-queue-csv",
            queue_csv,
            "--out-ligand-json",
            ligand_json,
            "--out-summary-json",
            stage1_summary,
            "--out-summary-md",
            stage1_md,
        ]
        stage1_cmd.append("--require-native-path" if bool(args.require_native_path) else "--no-require-native-path")
        rec1 = _run_cmd(stage1_cmd)
    if not rec1["ok"]:
        payload = {
            "pass": False,
            "failed_stage": "stage1_ligand_mapping",
            "stages": {
                "stage_lock": stage_lock,
                "stage0_leakage_audit": rec0,
                "stage1_ligand_mapping": rec1,
            },
            "artifacts": {"summary_json": f"{out_prefix}_summary.json"},
        }
        return _finalize_and_write(out_prefix, payload, args)

    min_eval_pos_keys = int(max(0, int(args.stage1_min_eval_positive_keys)))
    min_eval_pos_3d_ready_keys = int(max(0, int(args.stage1_min_eval_positive_3d_ready_keys)))
    if bool(args.stage1_require_positive_3d_ready) and min_eval_pos_3d_ready_keys <= 0:
        min_eval_pos_3d_ready_keys = int(min_eval_pos_keys)

    if (not resume_stage3_only) and ((min_eval_pos_keys > 0) or (min_eval_pos_3d_ready_keys > 0)):
        check_eval_roles = [x.strip() for x in str(args.stage1_positive_check_eval_roles).split(",") if x.strip()]
        if not check_eval_roles:
            check_eval_roles = [x.strip() for x in str(args.ranking_eval_roles).split(",") if x.strip()]
        labels_csv_for_check = str(args.stage1_positive_check_labels_csv or args.ranking_labels_csv)
        split_csv_for_check = str(args.stage1_positive_check_split_csv or args.eval_split_csv)
        stage1_positive_check = _stage1_eval_positive_check(
            queue_csv=queue_csv,
            labels_csv=labels_csv_for_check,
            split_csv=split_csv_for_check,
            eval_roles=check_eval_roles,
            target_col=str(args.stage1_positive_check_target_col),
            ligand_col=str(args.stage1_positive_check_ligand_col),
            role_col=str(args.stage1_positive_check_role_col),
            binder_col=str(args.stage1_positive_check_binder_col),
            require_3d_ready=bool(args.stage1_require_positive_3d_ready),
            require_native_path_exists=bool(args.stage1_require_native_path_for_positive_check),
        )
        eval_in_queue = int(stage1_positive_check.get("rows_eval_positive_in_queue", 0) or 0)
        eval_3d_ready = int(stage1_positive_check.get("rows_eval_positive_3d_ready", 0) or 0)
        if (
            (not bool(stage1_positive_check.get("ok", False)))
            or (eval_in_queue < int(min_eval_pos_keys))
            or (eval_3d_ready < int(min_eval_pos_3d_ready_keys))
        ):
            payload = {
                "pass": False,
                "failed_stage": "stage1_eval_positive_check",
                "stages": {
                    "stage_lock": stage_lock,
                    "stage0_leakage_audit": rec0,
                    "stage1_ligand_mapping": rec1,
                    "stage1_eval_positive_check": stage1_positive_check,
                },
                "artifacts": {"summary_json": f"{out_prefix}_summary.json"},
            }
            return _finalize_and_write(out_prefix, payload, args)

    stage2_traj_prefix = f"{out_prefix}_stage2_traj"
    generated_trajectory_root = str(args.trajectory_root).strip()
    rec_traj: Optional[Dict[str, Any]] = None
    if resume_stage3_only:
        if (not generated_trajectory_root) and bool(heavy_paths.get("enabled", False)):
            generated_trajectory_root = str(heavy_paths.get("stage2_trajectory_root", ""))
        if not generated_trajectory_root:
            generated_trajectory_root = f"{stage2_traj_prefix}_frames"
        if not os.path.exists(generated_trajectory_root):
            payload = {
                "pass": False,
                "failed_stage": "stage2_trajectory_generation",
                "stages": {
                    "stage_lock": stage_lock,
                    "stage0_leakage_audit": rec0,
                    "stage1_ligand_mapping": rec1,
                    "stage1_eval_positive_check": stage1_positive_check,
                    "stage2_trajectory_generation": {
                        "ok": False,
                        "skipped": True,
                        "resume_stage3_only": True,
                        "stderr_tail": f"trajectory root missing for resume-stage3-only: {generated_trajectory_root}",
                    },
                },
                "artifacts": {"summary_json": f"{out_prefix}_summary.json"},
            }
            return _finalize_and_write(out_prefix, payload, args)
        rec_traj = {"ok": True, "skipped": True, "reused": True, "resume_stage3_only": True, "cmd": [], "cmd_str": ""}
    elif bool(args.run_trajectory_sim):
        if str(traj_stage2_diag.get("error", "")).strip():
            payload = {
                "pass": False,
                "failed_stage": "stage2_traj_prod_preset_preflight",
                "traj_prod": traj_prod_summary,
                "stages": {
                    "stage_lock": stage_lock,
                    "stage0_leakage_audit": rec0,
                    "stage1_ligand_mapping": rec1,
                    "stage1_eval_positive_check": stage1_positive_check,
                },
                "traj_stage2_preset_diagnostics": traj_stage2_diag,
                "artifacts": {"summary_json": f"{out_prefix}_summary.json"},
            }
            return _finalize_and_write(out_prefix, payload, args)
        if (not generated_trajectory_root):
            if bool(heavy_paths.get("enabled", False)):
                generated_trajectory_root = str(heavy_paths.get("stage2_trajectory_root", ""))
            if not generated_trajectory_root:
                generated_trajectory_root = f"{stage2_traj_prefix}_frames"
        trajectory_engine_mode = str(args.trajectory_engine_mode).strip().lower()
        if trajectory_engine_mode not in {"proxy", "rust_hip"}:
            raise ValueError("--trajectory-engine-mode must be proxy|rust_hip")
        traj_frame_output_format = str(args.traj_frame_output_format).strip().lower()
        if (
            bool(getattr(args, "traj_auto_fast_output", True))
            and bool(getattr(args, "stage3_score_only", True))
            and int(getattr(args, "stage3_delivery_topk_global", 0) or 0) <= 0
            and int(getattr(args, "stage3_delivery_topk_per_target", 0) or 0) <= 0
            and traj_frame_output_format == "pdb_files"
        ):
            # Score-only HTVS runs do not need per-frame PDB fanout. Prefer sharded
            # NPZ to keep stage2 compute-bound instead of file-I/O-bound.
            traj_frame_output_format = "npz_bundle"
        traj_script = (
            "tools/generate_ligand_trajectory_engine.py"
            if trajectory_engine_mode == "rust_hip"
            else "tools/generate_ligand_trajectory_batch.py"
        )
        traj_cmd = [
            sys.executable,
            traj_script,
            "--queue-csv",
            queue_csv,
            "--out-root",
            generated_trajectory_root,
            "--frames",
            str(int(traj_frames)),
            "--write-every",
            str(int(args.traj_write_every)),
            "--frame-output-format",
            str(traj_frame_output_format),
            "--seed",
            str(int(args.traj_seed)),
            "--step-size",
            str(float(args.traj_step_size)),
            "--noise-scale",
            str(float(args.traj_noise_scale)),
            "--pocket-attract-base",
            str(float(args.traj_pocket_attract_base)),
            "--protein-repulse",
            str(float(args.traj_protein_repulse)),
            "--bond-k",
            str(float(args.traj_bond_k)),
            "--repulse-cutoff-A",
            str(float(args.traj_repulse_cutoff_A)),
            "--max-pocket-radius-A",
            str(float(args.traj_max_pocket_radius_A)),
            "--native-path-col",
            str(args.native_path_col),
            "--out-manifest-csv",
            f"{stage2_traj_prefix}_manifest.csv",
            "--out-summary-json",
            f"{stage2_traj_prefix}_summary.json",
            "--out-summary-md",
            f"{stage2_traj_prefix}_summary.md",
            "--out-progress-json",
            f"{stage2_traj_prefix}_progress.json",
            "--progress-every-jobs",
            "25",
        ]
        if trajectory_engine_mode == "rust_hip":
            traj_cmd.extend(
                [
                    "--npz-compression",
                    str(getattr(args, "traj_npz_compression", "store")),
                    "--npz-layout",
                    str(getattr(args, "traj_npz_layout", "flat_shard")),
                    "--npz-shard-size",
                    str(int(getattr(args, "traj_npz_shard_size", 512))),
                    "--engine-cache-max-entries",
                    str(int(getattr(args, "traj_engine_cache_max_entries", 16))),
                    "--job-batch-size",
                    str(int(getattr(args, "traj_job_batch_size", 0))),
                    "--job-batch-autotune-candidates",
                    str(traj_stage2_settings["traj_job_batch_autotune_candidates"]),
                    "--job-batch-autotune-frames",
                    str(int(getattr(args, "traj_job_batch_autotune_frames", 12))),
                    "--writer-workers",
                    str(int(traj_stage2_settings["traj_writer_workers"])),
                    "--writer-mode",
                    str(getattr(args, "traj_writer_mode", "process")),
                    "--writer-max-pending",
                    str(int(traj_stage2_settings["traj_writer_max_pending"])),
                ]
            )
        if trajectory_engine_mode == "rust_hip":
            traj_cmd.extend(
                [
                    "--dt-fs",
                    str(float(args.traj_dt_fs)),
                    "--friction",
                    str(float(args.traj_friction)),
                    "--kT",
                    str(float(args.traj_kT)),
                    "--force-clip",
                    str(float(args.traj_force_clip)),
                    "--box-size-A",
                    str(float(args.traj_box_size_A)),
                    "--ff-sigma",
                    str(float(args.traj_ff_sigma)),
                    "--ff-eps-solv",
                    str(float(args.traj_ff_eps_solv)),
                    "--force-backend",
                    str(args.traj_force_backend),
                    "--strategy-mode",
                    str(args.traj_strategy_mode),
                    "--dynamic-adress-min-affinity",
                    str(float(traj_stage2_settings["traj_dynamic_adress_min_affinity"])),
                    "--dynamic-adress-max-protein-residues",
                    str(int(traj_stage2_settings["traj_dynamic_adress_max_protein_residues"])),
                    "--dynamic-adress-min-ligand-mw",
                    str(float(args.traj_dynamic_adress_min_ligand_mw)),
                    "--dynamic-adress-fraction",
                    str(float(traj_stage2_settings["traj_dynamic_adress_fraction"])),
                    "--dynamic-adress-base-radius-A",
                    str(float(traj_stage2_settings["traj_dynamic_adress_base_radius_A"])),
                    "--dynamic-adress-affinity-radius-scale",
                    str(float(traj_stage2_settings["traj_dynamic_adress_affinity_radius_scale"])),
                    "--dynamic-adress-mw-radius-scale",
                    str(float(traj_stage2_settings["traj_dynamic_adress_mw_radius_scale"])),
                    "--dynamic-adress-max-all-atom-radius-A",
                    str(float(traj_stage2_settings["traj_dynamic_adress_max_all_atom_radius_A"])),
                    "--dynamic-adress-max-atom-ratio",
                    str(float(traj_stage2_settings["traj_dynamic_adress_max_atom_ratio"])),
                    "--dynamic-adress-force-targets",
                    str(args.traj_dynamic_adress_force_targets),
                ]
            )
            traj_cmd.extend(_traj_prod_stage2_args(args, mode=mode, traj_frames=int(traj_frames)))
            traj_cmd.append(
                "--dynamic-adress-cap-force-core-on-radius"
                if bool(args.traj_dynamic_adress_cap_force_core_on_radius)
                else "--no-dynamic-adress-cap-force-core-on-radius"
            )
            traj_cmd.append("--require-rust-hip" if bool(args.traj_require_rust_hip) else "--no-require-rust-hip")
            traj_cmd.append(
                "--dynamic-core-fallback-on-oom"
                if bool(args.traj_dynamic_core_fallback_on_oom)
                else "--no-dynamic-core-fallback-on-oom"
            )
            traj_cmd.append(
                "--abort-on-runtime-error"
                if bool(args.traj_abort_on_runtime_error)
                else "--no-abort-on-runtime-error"
            )
            traj_cmd.append(
                "--abort-on-cpu-backend"
                if bool(args.traj_abort_on_cpu_backend)
                else "--no-abort-on-cpu-backend"
            )
        traj_cmd.append("--fail-on-missing-native" if bool(args.require_native_path) else "--no-fail-on-missing-native")
        rec_traj = _run_cmd(traj_cmd)
        if isinstance(rec_traj, dict):
            rec_traj["traj_stage2_settings"] = traj_stage2_settings
            rec_traj["traj_stage2_preset_diagnostics"] = traj_stage2_diag
            rec_traj["traj_prod"] = traj_prod_summary
        if not rec_traj["ok"]:
            payload = {
                "pass": False,
                "failed_stage": "stage2_trajectory_generation",
                "traj_prod": traj_prod_summary,
                "stages": {
                    "stage0_leakage_audit": rec0,
                    "stage1_ligand_mapping": rec1,
                    "stage1_eval_positive_check": stage1_positive_check,
                    "stage2_trajectory_generation": rec_traj,
                },
                "artifacts": {"summary_json": f"{out_prefix}_summary.json"},
            }
            return _finalize_and_write(out_prefix, payload, args)
    elif not generated_trajectory_root:
        raise ValueError("trajectory source missing: set --trajectory-root or enable --run-trajectory-sim")
    if isinstance(rec_traj, dict):
        rec_traj.setdefault("traj_stage2_settings", traj_stage2_settings)
        rec_traj.setdefault("traj_stage2_preset_diagnostics", traj_stage2_diag)
        rec_traj.setdefault("traj_prod", traj_prod_summary)

    stage2_prefix = f"{out_prefix}_stage2"
    stage2_cmd = [
        sys.executable,
        "tools/run_ligand_residual_meta_cycle.py",
        "--ligand-queue-csv",
        queue_csv,
        "--date-tag",
        date_tag,
        "--targets",
        str(args.targets),
        "--out-prefix",
        stage2_prefix,
        "--priority-topk",
        str(int(args.priority_topk)),
        "--priority-bonus",
        str(float(args.priority_bonus)),
        "--hard-mining-topk",
        str(int(args.hard_mining_topk)),
        "--curriculum-base-manifest-csv",
        str(args.curriculum_base_manifest_csv),
        "--curriculum-max-targets",
        str(int(args.curriculum_max_targets)),
        "--curriculum-checkpoint-dir",
        str(args.curriculum_checkpoint_dir),
        "--curriculum-out-json",
        str(args.curriculum_out_json),
        "--curriculum-summary-json",
        str(args.curriculum_summary_json),
        "--curriculum-summary-csv",
        str(args.curriculum_summary_csv),
        "--accuracy-external-csv",
        str(args.accuracy_external_csv),
        "--stage2-csv",
        str(args.stage2_csv),
        "--claim-policy-json",
        str(args.claim_policy_json),
        "--claim-strict-summary-json",
        str(args.claim_strict_summary_json),
        "--claim-accuracy-external-csv",
        str(args.claim_accuracy_external_csv),
        "--claim-thermo-input-csv",
        str(args.claim_thermo_input_csv),
        "--claim-kinetics-input-csv",
        str(args.claim_kinetics_input_csv),
        "--claim-out-prefix",
        str(args.claim_out_prefix),
    ]
    if bool(args.skip_curriculum_training):
        stage2_cmd.append("--skip-curriculum-training")
    else:
        stage2_cmd.append("--no-skip-curriculum-training")
    if bool(args.skip_claim_correction):
        stage2_cmd.append("--skip-claim-correction")
    else:
        stage2_cmd.append("--no-skip-claim-correction")
    if bool(args.dry_run):
        stage2_cmd.append("--dry-run")
    else:
        stage2_cmd.append("--no-dry-run")

    rec2 = _run_cmd(stage2_cmd)
    if not rec2["ok"]:
        payload = {
            "pass": False,
            "failed_stage": "stage2_residual_meta",
            "stages": {
                "stage0_leakage_audit": rec0,
                "stage1_ligand_mapping": rec1,
                "stage1_eval_positive_check": stage1_positive_check,
                "stage2_trajectory_generation": rec_traj,
                "stage2_residual_meta": rec2,
            },
            "artifacts": {"summary_json": f"{out_prefix}_summary.json"},
        }
        return _finalize_and_write(out_prefix, payload, args)

    stage3_prefix = f"{out_prefix}_stage3"
    stage3_out_dir = (
        str(heavy_paths.get("stage3_delivery_dir"))
        if bool(heavy_paths.get("enabled", False))
        else f"{stage3_prefix}_delivery"
    )
    stage3_cmd = [
        sys.executable,
        "tools/run_ligand_backmapping_scoring.py",
        "--queue-csv",
        queue_csv,
        "--stage2-manifest-csv",
        f"{stage2_traj_prefix}_manifest.csv",
        "--trajectory-root",
        str(generated_trajectory_root),
        "--trajectory-glob",
        str(args.trajectory_glob),
        "--contact-cutoff-A",
        str(float(args.contact_cutoff_A)),
        "--min-frames",
        str(int(args.stage3_min_frames)),
        "--max-jobs",
        str(max_jobs_score),
        "--out-dir",
        stage3_out_dir,
        "--out-scores-csv",
        f"{stage3_prefix}_scores.csv",
        "--out-summary-json",
        f"{stage3_prefix}_summary.json",
        "--out-summary-md",
        f"{stage3_prefix}_summary.md",
        "--workers",
        str(int(max(0, int(getattr(args, "stage3_workers", 0))))),
        "--parallel-threshold",
        str(int(max(1, int(getattr(args, "stage3_parallel_threshold", 2))))),
        "--score-only" if bool(getattr(args, "stage3_score_only", True)) else "--no-score-only",
        "--make-bundle-zip" if bool(args.make_bundle_zip) else "--no-make-bundle-zip",
    ]
    if str(getattr(args, "stage3_aux_model_checkpoint", "")).strip():
        stage3_cmd.extend(
            [
                "--aux-model-checkpoint",
                str(args.stage3_aux_model_checkpoint),
                "--aux-score-weight",
                str(float(getattr(args, "stage3_aux_score_weight", 0.35))),
            ]
        )
    stage3_cmd.extend(
        [
            "--residual-prototype-enabled"
            if bool(getattr(args, "stage3_residual_prototype_enabled", False))
            else "--no-residual-prototype-enabled",
            "--residual-prototype-mode",
            str(getattr(args, "stage3_residual_prototype_mode", "shadow_only")),
            "--residual-prototype-family",
            str(getattr(args, "stage3_residual_prototype_family", "")),
            "--residual-prototype-runtime-hook-ready"
            if bool(getattr(args, "stage3_residual_prototype_runtime_hook_ready", False))
            else "--no-residual-prototype-runtime-hook-ready",
        ]
    )
    if str(getattr(args, "stage3_residual_prototype_spec_json", "")).strip():
        stage3_cmd.extend(
            [
                "--residual-prototype-spec-json",
                str(args.stage3_residual_prototype_spec_json),
            ]
        )
    if getattr(args, "stage3_residual_prototype_max_abs_delta_score", None) is not None:
        stage3_cmd.extend(
            [
                "--residual-prototype-max-abs-delta-score",
                str(float(args.stage3_residual_prototype_max_abs_delta_score)),
            ]
        )
    if getattr(args, "stage3_residual_prototype_yellow_band_abs_delta_score", None) is not None:
        stage3_cmd.extend(
            [
                "--residual-prototype-yellow-band-abs-delta-score",
                str(float(args.stage3_residual_prototype_yellow_band_abs_delta_score)),
            ]
        )
    stage3_cmd.extend(
        [
            "--score-reference-scaling-mode",
            str(getattr(args, "stage3_score_reference_scaling_mode", "run_local")),
        ]
    )
    if str(getattr(args, "stage3_score_reference_stats_json", "")).strip():
        stage3_cmd.extend(
            [
                "--score-reference-stats-json",
                str(args.stage3_score_reference_stats_json),
            ]
        )
    # Keep calibration fit-role coverage inside stage3 sampling window.
    # Without fit keys here, stage4 can become fit_rows_total=0.
    stage3_priority_roles = _merge_roles_csv(
        str(args.calibration_fit_roles),
        str(args.ranking_eval_roles),
        str(args.ranking_ood_eval_roles),
    )
    if str(args.eval_split_csv).strip() and str(stage3_priority_roles).strip():
        stage3_cmd.extend(
            [
                "--priority-split-csv",
                str(args.eval_split_csv),
                "--priority-roles",
                str(stage3_priority_roles),
                "--priority-split-role-col",
                "role",
                "--priority-split-target-col",
                "target",
                "--priority-split-ligand-col",
                "ligand_id",
            ]
        )
    if bool(args.allow_missing_trajectory):
        stage3_cmd.append("--allow-missing-trajectory")
    else:
        stage3_cmd.append("--no-allow-missing-trajectory")
    rec3 = _run_cmd(stage3_cmd)
    if not rec3["ok"]:
        payload = {
            "pass": False,
            "failed_stage": "stage3_backmapping_scoring",
            "stages": {
                "stage0_leakage_audit": rec0,
                "stage1_ligand_mapping": rec1,
                "stage1_eval_positive_check": stage1_positive_check,
                "stage2_trajectory_generation": rec_traj,
                "stage2_residual_meta": rec2,
                "stage3_backmapping_scoring": rec3,
            },
            "artifacts": {"summary_json": f"{out_prefix}_summary.json"},
        }
        return _finalize_and_write(out_prefix, payload, args)

    stage3_scores_csv = f"{stage3_prefix}_scores.csv"
    stage3b_prefix = f"{out_prefix}_stage3b_physics_refinement"
    stage3b_scores_csv = f"{stage3b_prefix}_scores.csv"
    stage3b_summary_json = f"{stage3b_prefix}_summary.json"
    stage3b_shortlist_csv = f"{stage3b_prefix}_shortlist.csv"
    stage4_prefix = f"{out_prefix}_stage4_calibration"
    stage5_prefix = f"{out_prefix}_stage5_ranking"
    stage4_scores_csv = f"{stage4_prefix}_scores.csv"
    stage4_summary_json = f"{stage4_prefix}_summary.json"
    stage5_summary_json = f"{stage5_prefix}_summary.json"
    admet_surface_json = f"{out_prefix}_admet_surface.json"
    physics_refinement_enabled = bool(getattr(args, "run_physics_refinement", False))
    physics_refinement_use_downstream = bool(
        physics_refinement_enabled and bool(getattr(args, "physics_refinement_use_refined_scores_downstream", True))
    )
    physics_refinement_use_calibration_proxy = bool(
        physics_refinement_use_downstream
        and bool(getattr(args, "physics_refinement_use_refined_proxy_for_calibration", True))
    )
    rec3b: Dict[str, Any] = {
        "ok": True,
        "skipped": not physics_refinement_enabled,
        "cmd": [],
        "cmd_str": "",
    }
    rec4: Dict[str, Any] = {"ok": True, "skipped": True, "cmd": [], "cmd_str": ""}
    rec45: Dict[str, Any] = {"ok": True, "skipped": True, "cmd": [], "cmd_str": ""}
    rec5: Dict[str, Any] = {"ok": True, "skipped": True, "cmd": [], "cmd_str": ""}
    rec3_delivery: Dict[str, Any] = {"ok": True, "skipped": True, "cmd": [], "cmd_str": ""}
    rec_admet: Dict[str, Any] = {"ok": True, "skipped": True, "cmd": [], "cmd_str": ""}
    stage3_scores_csv_for_downstream = stage3_scores_csv
    stage3_delivery_scores_csv = stage3_scores_csv
    calibration_proxy_col_for_stage4 = str(args.calibration_proxy_col)
    physics_refinement_summary: Dict[str, Any] = {}

    if physics_refinement_enabled:
        stage3b_cmd = [
            sys.executable,
            "tools/run_ligand_physics_refinement.py",
            "--scores-csv",
            stage3_scores_csv,
            "--score-col",
            str(getattr(args, "physics_refinement_score_col", "")),
            "--base-proxy-col",
            str(args.calibration_proxy_col),
            "--target-col",
            "target",
            "--ligand-col",
            "ligand_id",
            "--topk-global",
            str(int(max(0, int(getattr(args, "physics_refinement_topk_global", 0))))),
            "--topk-per-target",
            str(int(max(0, int(getattr(args, "physics_refinement_topk_per_target", 0))))),
            "--selection-mode",
            str(getattr(args, "physics_refinement_selection_mode", "union")),
            "--refinement-mode",
            str(getattr(args, "physics_refinement_mode", "explicit_water_surrogate")),
            "--backend",
            str(getattr(args, "physics_refinement_backend", "deterministic_surrogate_wrapper_v1")),
            "--refined-energy-col",
            str(getattr(args, "physics_refinement_refined_energy_col", "binding_energy_explicit_water_recheck_kcal_mol_proxy")),
            "--refined-rank-col",
            str(getattr(args, "physics_refinement_refined_rank_col", "binding_score_stronger_physics_v1")),
            "--out-csv",
            stage3b_scores_csv,
            "--out-shortlist-csv",
            stage3b_shortlist_csv,
            "--out-shortlist-json",
            f"{stage3b_prefix}_shortlist.json",
            "--out-json",
            stage3b_summary_json,
            "--out-md",
            f"{stage3b_prefix}_summary.md",
        ]
        rec3b = _run_cmd(stage3b_cmd)
        if not rec3b["ok"]:
            payload = {
                "pass": False,
                "failed_stage": "stage3b_physics_refinement",
                "stages": {
                    "stage0_leakage_audit": rec0,
                    "stage1_ligand_mapping": rec1,
                    "stage1_eval_positive_check": stage1_positive_check,
                    "stage2_trajectory_generation": rec_traj,
                    "stage2_residual_meta": rec2,
                    "stage3_backmapping_scoring": rec3,
                    "stage3b_physics_refinement": rec3b,
                },
                "artifacts": {"summary_json": f"{out_prefix}_summary.json"},
            }
            return _finalize_and_write(out_prefix, payload, args)
        physics_refinement_summary = _read_json_if_exists(stage3b_summary_json)
        if physics_refinement_use_downstream:
            stage3_scores_csv_for_downstream = stage3b_scores_csv
            stage3_delivery_scores_csv = stage3b_scores_csv
        if physics_refinement_use_calibration_proxy:
            calibration_proxy_col_for_stage4 = str(
                getattr(args, "physics_refinement_refined_energy_col", "binding_energy_explicit_water_recheck_kcal_mol_proxy")
            )

    physics_refinement_runtime: Dict[str, Any] = {
        "enabled": bool(physics_refinement_enabled),
        "use_refined_scores_downstream": bool(physics_refinement_use_downstream),
        "use_refined_proxy_for_calibration": bool(physics_refinement_use_calibration_proxy),
        "refinement_mode": str(
            physics_refinement_summary.get("refinement_mode", getattr(args, "physics_refinement_mode", ""))
            if physics_refinement_enabled
            else ""
        ),
        "refinement_backend": str(
            physics_refinement_summary.get("refinement_backend", getattr(args, "physics_refinement_backend", ""))
            if physics_refinement_enabled
            else ""
        ),
        "score_col_requested": str(getattr(args, "physics_refinement_score_col", "")),
        "score_col_used": str(physics_refinement_summary.get("score_col_used", "") or ""),
        "base_proxy_col_used": str(physics_refinement_summary.get("base_proxy_col_used", "") or str(args.calibration_proxy_col)),
        "refined_energy_col": str(
            physics_refinement_summary.get(
                "refined_energy_col",
                getattr(args, "physics_refinement_refined_energy_col", ""),
            )
            or ""
        ),
        "refined_rank_col": str(
            physics_refinement_summary.get(
                "refined_rank_col",
                getattr(args, "physics_refinement_refined_rank_col", ""),
            )
            or ""
        ),
        "input_scores_csv": stage3_scores_csv,
        "output_scores_csv": stage3b_scores_csv if physics_refinement_enabled else "",
        "downstream_scores_csv": stage3_scores_csv_for_downstream,
        "summary_json": stage3b_summary_json if physics_refinement_enabled else "",
        "shortlist_csv": stage3b_shortlist_csv if physics_refinement_enabled else "",
        "selected_count": int(physics_refinement_summary.get("selected_count", 0) or 0),
        "selected_fraction": (
            float(physics_refinement_summary.get("selected_fraction"))
            if physics_refinement_summary.get("selected_fraction") is not None
            else None
        ),
        "selected_metrics": (
            dict(physics_refinement_summary.get("selected_metrics", {}))
            if isinstance(physics_refinement_summary.get("selected_metrics"), dict)
            else {}
        ),
        "warnings": [str(x) for x in physics_refinement_summary.get("warnings", []) if str(x).strip()],
        "calibration_proxy_col_used": str(calibration_proxy_col_for_stage4),
    }
    scored_csv_for_gate = stage3_scores_csv_for_downstream

    if bool(args.run_calibration):
        stage4_cmd = [
            sys.executable,
            "tools/calibrate_ligand_mmpbsa_proxy.py",
            "--scores-csv",
            stage3_scores_csv_for_downstream,
            "--reference-csv",
            str(args.calibration_reference_csv),
            "--proxy-col",
            str(calibration_proxy_col_for_stage4),
            "--reference-value-col",
            str(args.calibration_reference_value_col),
            "--join-target-col",
            "target",
            "--join-ligand-col",
            "ligand_id",
            "--split-csv",
            str(args.eval_split_csv),
            "--fit-roles",
            str(args.calibration_fit_roles),
            "--split-role-col",
            "role",
            "--split-target-col",
            "target",
            "--split-ligand-col",
            "ligand_id",
            "--require-split-for-fit" if bool(args.require_split_for_calibration) else "--no-require-split-for-fit",
            "--min-pairs-to-fit",
            str(int(args.calibration_min_pairs_to_fit)),
            "--clip-abs",
            str(float(args.calibration_clip_abs)),
            "--out-col",
            str(args.calibration_out_col),
            "--out-csv",
            stage4_scores_csv,
            "--out-model-json",
            f"{stage4_prefix}_model.json",
            "--out-json",
            stage4_summary_json,
            "--out-md",
            f"{stage4_prefix}_summary.md",
        ]
        rec4 = _run_cmd(stage4_cmd)
        if not rec4["ok"]:
            payload = {
                "pass": False,
                "failed_stage": "stage4_calibration",
                "stages": {
                    "stage0_leakage_audit": rec0,
                    "stage1_ligand_mapping": rec1,
                    "stage1_eval_positive_check": stage1_positive_check,
                    "stage2_trajectory_generation": rec_traj,
                    "stage2_residual_meta": rec2,
                    "stage3_backmapping_scoring": rec3,
                    "stage3b_physics_refinement": rec3b,
                    "stage4_calibration": rec4,
                },
                "artifacts": {"summary_json": f"{out_prefix}_summary.json"},
            }
            return _finalize_and_write(out_prefix, payload, args)
        stage4_payload = _read_json_if_exists(stage4_summary_json)
        fit_unique_keys = int(float(stage4_payload.get("fit_unique_keys", 0) or 0))
        min_fit_unique_keys = int(max(0, int(args.calibration_min_fit_unique_keys)))
        if fit_unique_keys < min_fit_unique_keys:
            payload = {
                "pass": False,
                "failed_stage": "stage4_calibration",
                "stages": {
                    "stage0_leakage_audit": rec0,
                    "stage1_ligand_mapping": rec1,
                    "stage1_eval_positive_check": stage1_positive_check,
                    "stage2_trajectory_generation": rec_traj,
                    "stage2_residual_meta": rec2,
                    "stage3_backmapping_scoring": rec3,
                    "stage3b_physics_refinement": rec3b,
                    "stage4_calibration": rec4,
                    "stage4_calibration_summary": stage4_payload,
                },
                "artifacts": {"summary_json": f"{out_prefix}_summary.json"},
            }
            return _finalize_and_write(out_prefix, payload, args)
        scored_csv_for_gate = stage4_scores_csv

    if bool(args.enforce_zero_overlap):
        stage45_prefix = f"{out_prefix}_stage45_integrity"
        stage45_cmd = [
            sys.executable,
            "tools/validate_ligand_eval_integrity.py",
            "--split-csv",
            str(args.eval_split_csv),
            "--scores-csv",
            str(scored_csv_for_gate),
            "--expected-keys-csv",
            str(queue_csv),
            "--labels-csv",
            str(args.ranking_labels_csv),
            "--labels-binder-col",
            str(args.ranking_binder_col),
            "--fit-roles",
            str(args.calibration_fit_roles),
            "--eval-roles",
            f"{str(args.ranking_eval_roles)},{str(args.ranking_ood_eval_roles)}",
            "--min-observed-fit-coverage-ratio",
            str(float(args.stage45_min_observed_fit_coverage_ratio)),
            "--min-observed-eval-coverage-ratio",
            str(float(args.stage45_min_observed_eval_coverage_ratio)),
            "--min-observed-eval-positive-coverage-ratio",
            str(float(args.stage45_min_observed_eval_positive_coverage_ratio)),
            "--out-json",
            f"{stage45_prefix}_summary.json",
            "--out-csv",
            f"{stage45_prefix}_summary.csv",
            "--out-md",
            f"{stage45_prefix}_summary.md",
        ]
        rec45 = _run_cmd(stage45_cmd)
        if not rec45["ok"]:
            payload = {
                "pass": False,
                "failed_stage": "stage45_eval_integrity",
                "stages": {
                    "stage0_leakage_audit": rec0,
                    "stage1_ligand_mapping": rec1,
                    "stage1_eval_positive_check": stage1_positive_check,
                    "stage2_trajectory_generation": rec_traj,
                    "stage2_residual_meta": rec2,
                    "stage3_backmapping_scoring": rec3,
                    "stage3b_physics_refinement": rec3b,
                    "stage4_calibration": rec4,
                    "stage45_eval_integrity": rec45,
                },
                "artifacts": {"summary_json": f"{out_prefix}_summary.json"},
            }
            return _finalize_and_write(out_prefix, payload, args)

    if bool(args.run_ranking_eval):
        ranking_score_col = str(args.ranking_score_col)
        ranking_probability_score_col = str(args.ranking_probability_score_col or "").strip()
        ranking_score_fallback_note = ""
        refinement_rank_fallback = str(physics_refinement_runtime.get("refined_rank_col", "") or "")
        refinement_energy_fallback = str(physics_refinement_runtime.get("refined_energy_col", "") or "")
        scored_cols: set[str] = set()
        try:
            scored_cols = set(pd.read_csv(scored_csv_for_gate, nrows=1).columns)
        except Exception:
            scored_cols = set()
        # Keep ranking/discrimination metrics on raw proxy score by default,
        # while calibration quality (Brier/ECE) can use calibrated score.
        if bool(args.run_calibration):
            if ranking_score_col == str(args.calibration_out_col):
                ranking_score_col = str(calibration_proxy_col_for_stage4)
            if not ranking_probability_score_col:
                ranking_probability_score_col = str(args.calibration_out_col)
        else:
            if ranking_score_col == str(args.calibration_out_col):
                ranking_score_col = str(calibration_proxy_col_for_stage4)
            if not ranking_probability_score_col:
                ranking_probability_score_col = str(ranking_score_col)
        if scored_cols and (ranking_score_col not in scored_cols):
            fallback_candidates: List[str] = []
            if physics_refinement_use_downstream:
                for cand in [refinement_rank_fallback, refinement_energy_fallback]:
                    if str(cand).strip():
                        fallback_candidates.append(str(cand))
            fallback_candidates.extend(
                [
                    "binding_score_composite_v7_residual_active",
                    "binding_score_composite_v7",
                    "binding_score_composite_v6",
                    "binding_score_composite_v5",
                    str(calibration_proxy_col_for_stage4),
                    str(args.calibration_proxy_col),
                    "binding_score_composite_v3",
                    "binding_score_composite_v2",
                    "binding_energy_mmpbsa_kcal_mol_proxy",
                    "binding_energy_proxy",
                ]
            )
            seen_candidates = set()
            for cand in fallback_candidates:
                if cand in seen_candidates:
                    continue
                seen_candidates.add(cand)
                if cand in scored_cols:
                    ranking_score_fallback_note = f"ranking score column fallback: {ranking_score_col} -> {cand}"
                    ranking_score_col = cand
                    if (not ranking_probability_score_col) or (ranking_probability_score_col not in scored_cols):
                        ranking_probability_score_col = cand
                    break
        if scored_cols and ranking_probability_score_col and (ranking_probability_score_col not in scored_cols):
            if ranking_score_col in scored_cols:
                ranking_probability_score_col = ranking_score_col
            else:
                ranking_probability_score_col = ""
        stage5_cmd = [
            sys.executable,
            "tools/evaluate_ligand_ranking_metrics.py",
            "--scores-csv",
            scored_csv_for_gate,
            "--labels-csv",
            str(args.ranking_labels_csv),
            "--score-col",
            str(ranking_score_col),
            "--probability-score-col",
            str(ranking_probability_score_col),
            "--binder-col",
            str(args.ranking_binder_col),
            "--ref-energy-col",
            str(args.ranking_ref_energy_col),
            "--binder-threshold-kcal-mol",
            str(float(args.ranking_binder_threshold_kcal_mol)),
            "--split-csv",
            str(args.eval_split_csv),
            "--split-role-col",
            "role",
            "--split-target-col",
            "target",
            "--split-ligand-col",
            "ligand_id",
            "--expected-keys-csv",
            str(queue_csv),
            "--expected-target-col",
            "target",
            "--expected-ligand-col",
            "ligand_id",
            "--min-expected-score-coverage",
            str(float(args.ranking_min_expected_score_coverage)),
            "--eval-roles",
            str(args.ranking_eval_roles),
            "--ood-eval-roles",
            str(args.ranking_ood_eval_roles),
            "--require-split-for-eval" if bool(args.require_split_for_ranking) else "--no-require-split-for-eval",
            "--require-ood-eval" if bool(args.require_ood_eval) else "--no-require-ood-eval",
            "--topk-list",
            str(args.ranking_topk_list),
            "--bootstrap-n",
            str(int(args.ranking_bootstrap_n)),
            "--bootstrap-seed",
            str(int(args.ranking_bootstrap_seed)),
            "--bootstrap-bedroc-alpha",
            str(float(args.ranking_bootstrap_bedroc_alpha)),
            "--ece-bins",
            str(int(args.ranking_ece_bins)),
            "--probability-logit-scale",
            str(float(args.ranking_probability_logit_scale)),
            "--labels-driven-eval"
            if bool(args.ranking_labels_driven_eval)
            else "--no-labels-driven-eval",
            "--missing-score-policy",
            str(args.ranking_missing_score_policy),
            "--missing-score-worst-margin",
            str(float(args.ranking_missing_score_worst_margin)),
            "--out-detail-csv",
            f"{stage5_prefix}_rows.csv",
            "--out-topk-csv",
            f"{stage5_prefix}_topk.csv",
            "--out-unique-csv",
            f"{stage5_prefix}_unique.csv",
            "--out-json",
            stage5_summary_json,
            "--out-md",
            f"{stage5_prefix}_summary.md",
        ]
        if args.ranking_missing_score_worst_value is not None:
            stage5_cmd.extend(
                [
                    "--missing-score-worst-value",
                    str(float(args.ranking_missing_score_worst_value)),
                ]
            )
        rec5 = _run_cmd(stage5_cmd)
        if ranking_score_fallback_note:
            rec5.setdefault("note", ranking_score_fallback_note)
        if not rec5["ok"]:
            payload = {
                "pass": False,
                "failed_stage": "stage5_ranking_eval",
                "stages": {
                    "stage0_leakage_audit": rec0,
                    "stage1_ligand_mapping": rec1,
                    "stage1_eval_positive_check": stage1_positive_check,
                    "stage2_trajectory_generation": rec_traj,
                    "stage2_residual_meta": rec2,
                    "stage3_backmapping_scoring": rec3,
                    "stage3b_physics_refinement": rec3b,
                    "stage4_calibration": rec4,
                    "stage45_eval_integrity": rec45,
                    "stage5_ranking_eval": rec5,
                },
                "artifacts": {"summary_json": f"{out_prefix}_summary.json"},
            }
            return _finalize_and_write(out_prefix, payload, args)

    admet_cmd = [
        sys.executable,
        "tools/build_ligand_admet_surface.py",
        "--scores-csv",
        scored_csv_for_gate,
        "--out-json",
        admet_surface_json,
    ]
    rec_admet = _run_cmd(admet_cmd)
    if not rec_admet["ok"]:
        payload = {
            "pass": False,
            "failed_stage": "stage5b_admet_surface",
            "stages": {
                "stage0_leakage_audit": rec0,
                "stage1_ligand_mapping": rec1,
                "stage1_eval_positive_check": stage1_positive_check,
                "stage2_trajectory_generation": rec_traj,
                "stage2_residual_meta": rec2,
                "stage3_backmapping_scoring": rec3,
                "stage3b_physics_refinement": rec3b,
                "stage4_calibration": rec4,
                "stage45_eval_integrity": rec45,
                "stage5_ranking_eval": rec5,
                "stage5b_admet_surface": rec_admet,
            },
            "artifacts": {"summary_json": f"{out_prefix}_summary.json"},
        }
        return _finalize_and_write(out_prefix, payload, args)

    rank_payload_for_claim: Dict[str, Any] = {}
    gate_enforcement_mode = str(getattr(args, "gate_enforcement_mode", "operational")).strip().lower()
    if gate_enforcement_mode not in {"operational", "strict", "both"}:
        raise ValueError("--gate-enforcement-mode must be operational|strict|both")
    enforce_operational_gate = bool(args.enforce_operational_gate)
    enforce_strict_gate = bool(args.enforce_strict_gate) or gate_enforcement_mode in {"strict", "both"}

    gate_summary: Dict[str, Any] = {
        "enabled": bool(enforce_operational_gate),
        "pass": True,
        "failed_metrics": [],
        "warnings": [],
        "min_frames_observed": None,
        "mean_min_distance_A": None,
        "mean_min_distance_A_all": None,
        "mean_min_distance_A_source": None,
        "mean_min_distance_A_topk_k": None,
        "ranking_auc": None,
        "ranking_row_auc_aux": None,
        "ranking_unique_auc": None,
        "ranking_ood_unique_auc": None,
        "ranking_pr_auc": None,
        "ranking_ef1": None,
        "ranking_bedroc": None,
        "ranking_brier": None,
        "ranking_ece": None,
        "ranking_roc_auc_ci_low": None,
        "ranking_pr_auc_ci_low": None,
        "ranking_ef1_ci_low": None,
        "ranking_topk_hit_rate": None,
        "ranking_positive_count": None,
        "ranking_ood_positive_count": None,
        "ranking_score_col_used": None,
        "ranking_probability_score_col_used": None,
        "ranking_score_unique_ratio": None,
        "ranking_score_tie_ratio": None,
        "ranking_score_mode_ratio": None,
        "ranking_score_orientation_auc_delta": None,
        "ranking_score_orientation_suspect": None,
        "ranking_expected_score_coverage_ratio": None,
        "ranking_eval_unique_keys": None,
        "ranking_ood_unique_keys": None,
    }
    gate_df: Optional[pd.DataFrame] = None
    gate_mean_d_candidate: Optional[float] = None
    gate_mean_d_source: str = ""
    gate_mean_d_topk: Optional[int] = None
    gate_max_mean_distance = float(args.gate_max_mean_min_distance_A)
    gate_distance_source = str(getattr(args, "gate_mean_min_distance_source", "eval_unique_topk") or "eval_unique_topk").strip().lower()
    gate_distance_topk = int(max(1, int(getattr(args, "gate_mean_min_distance_topk", 200) or 200)))
    if bool(enforce_operational_gate):
        if not os.path.exists(scored_csv_for_gate):
            gate_summary["failed_metrics"].append(
                {"metric": "scores_csv_present", "value": scored_csv_for_gate, "threshold": "exists"}
            )
        else:
            try:
                gate_df = pd.read_csv(scored_csv_for_gate)
            except Exception:
                gate_df = None
            if gate_df is None or gate_df.empty:
                gate_summary["failed_metrics"].append({"metric": "scores_csv_nonempty", "value": 0, "threshold": ">0"})
            else:
                if "trajectory_frames" in gate_df.columns:
                    min_frames_obs = int(gate_df["trajectory_frames"].min())
                    gate_summary["min_frames_observed"] = min_frames_obs
                    if min_frames_obs < int(args.gate_min_frames):
                        gate_summary["failed_metrics"].append(
                            {
                                "metric": "min_trajectory_frames",
                                "value": min_frames_obs,
                                "threshold": int(args.gate_min_frames),
                            }
                        )
                if gate_max_mean_distance > 0 and ("mean_min_distance_A" in gate_df.columns):
                    mean_all = float(pd.to_numeric(gate_df["mean_min_distance_A"], errors="coerce").mean())
                    gate_summary["mean_min_distance_A_all"] = mean_all
                    if gate_distance_source == "scores_all_mean":
                        gate_mean_d_candidate = mean_all
                        gate_mean_d_source = "scores_all_mean"

        if bool(args.run_ranking_eval) and os.path.exists(stage5_summary_json):
            rank_payload = _read_json_if_exists(stage5_summary_json)
            rank_payload_for_claim = rank_payload if isinstance(rank_payload, dict) else {}
            metrics = rank_payload.get("metrics", {}) if isinstance(rank_payload.get("metrics"), dict) else {}
            metrics_unique = (
                rank_payload.get("metrics_unique", {}) if isinstance(rank_payload.get("metrics_unique"), dict) else {}
            )
            metrics_ci = rank_payload.get("metrics_ci", {}) if isinstance(rank_payload.get("metrics_ci"), dict) else {}
            if isinstance(rank_payload.get("score_col"), str):
                gate_summary["ranking_score_col_used"] = str(rank_payload.get("score_col"))
            if isinstance(rank_payload.get("probability_score_col"), str):
                gate_summary["ranking_probability_score_col_used"] = str(rank_payload.get("probability_score_col"))
            if gate_max_mean_distance > 0 and gate_distance_source in {"eval_unique_mean", "eval_unique_topk"}:
                rank_artifacts = rank_payload.get("artifacts", {}) if isinstance(rank_payload.get("artifacts"), dict) else {}
                unique_csv = str(rank_artifacts.get("unique_csv", "")).strip()
                score_col_for_sort = str(rank_payload.get("score_col", "")).strip()
                lower_better_rank = bool(rank_payload.get("lower_better", True))
                if unique_csv and os.path.exists(unique_csv):
                    try:
                        u = pd.read_csv(unique_csv)
                        if "mean_min_distance_A" in u.columns and (not u.empty):
                            u = u.copy()
                            override_report = _load_gate_distance_override_rows(
                                str(getattr(args, "gate_distance_override_csv", "") or "").strip(),
                                join_target="target",
                                join_ligand="ligand_id",
                            )
                            u, override_stats = _apply_gate_distance_overrides(
                                u,
                                override_report,
                                join_target="target",
                                join_ligand="ligand_id",
                            )
                            if bool(override_stats.get("requested", False)):
                                gate_summary["mean_min_distance_A_override_csv"] = str(
                                    override_stats.get("path", "") or ""
                                )
                                gate_summary["mean_min_distance_A_override_row_count"] = int(
                                    override_stats.get("row_count", 0) or 0
                                )
                                gate_summary["mean_min_distance_A_override_valid_row_count"] = int(
                                    override_stats.get("valid_row_count", 0) or 0
                                )
                                gate_summary["mean_min_distance_A_override_applied_count"] = int(
                                    override_stats.get("applied_count", 0) or 0
                                )
                                gate_summary["mean_min_distance_A_override_missing_count"] = int(
                                    override_stats.get("missing_count", 0) or 0
                                )
                                missing_row_keys = list(override_stats.get("missing_row_keys", []) or [])
                                if missing_row_keys:
                                    gate_summary["warnings"].append(
                                        f"gate distance override rows missing from unique band: {missing_row_keys}"
                                    )
                                for warn in [str(x) for x in override_stats.get("warnings", []) if str(x).strip()]:
                                    gate_summary["warnings"].append(warn)
                            if score_col_for_sort and (score_col_for_sort in u.columns):
                                u["_score_sort"] = pd.to_numeric(u[score_col_for_sort], errors="coerce")
                                u = u.sort_values("_score_sort", ascending=lower_better_rank, na_position="last").reset_index(drop=True)
                            dist = pd.to_numeric(u["mean_min_distance_A"], errors="coerce")
                            if gate_distance_source == "eval_unique_topk":
                                d_topk = int(min(gate_distance_topk, len(u)))
                                if d_topk > 0:
                                    gate_mean_d_candidate = float(pd.to_numeric(u.head(d_topk)["mean_min_distance_A"], errors="coerce").mean())
                                    gate_mean_d_source = (
                                        "eval_unique_topk+gate_distance_override"
                                        if int(gate_summary.get("mean_min_distance_A_override_applied_count", 0) or 0) > 0
                                        else "eval_unique_topk"
                                    )
                                    gate_mean_d_topk = int(d_topk)
                            else:
                                gate_mean_d_candidate = float(dist.mean())
                                gate_mean_d_source = (
                                    "eval_unique_mean+gate_distance_override"
                                    if int(gate_summary.get("mean_min_distance_A_override_applied_count", 0) or 0) > 0
                                    else "eval_unique_mean"
                                )
                        else:
                            gate_summary["warnings"].append(
                                "gate_mean_min_distance_source requested unique distance, but unique_csv lacks mean_min_distance_A"
                            )
                    except Exception as e:
                        gate_summary["warnings"].append(f"gate_mean_min_distance_source unique_csv parse failed: {e}")
                else:
                    gate_summary["warnings"].append(
                        "gate_mean_min_distance_source requested unique distance, but stage5 unique_csv is unavailable"
                    )
            if isinstance(rank_payload.get("observed_expected_score_coverage_ratio"), (int, float)):
                gate_summary["ranking_expected_score_coverage_ratio"] = float(
                    rank_payload.get("observed_expected_score_coverage_ratio")
                )
                if float(gate_summary["ranking_expected_score_coverage_ratio"]) < float(
                    args.gate_ranking_min_expected_score_coverage
                ):
                    gate_summary["failed_metrics"].append(
                        {
                            "metric": "ranking_expected_score_coverage_ratio",
                            "value": float(gate_summary["ranking_expected_score_coverage_ratio"]),
                            "threshold": float(args.gate_ranking_min_expected_score_coverage),
                        }
                    )
            topk = rank_payload.get("topk", []) if isinstance(rank_payload.get("topk"), list) else []
            topk_unique = rank_payload.get("topk_unique", []) if isinstance(rank_payload.get("topk_unique"), list) else []
            auc_row = metrics.get("roc_auc", None)
            auc_unique = metrics.get("roc_auc_unique_key", None)
            auc_ood_unique = metrics.get("roc_auc_ood_unique_key", None)
            pr_auc_unique = metrics.get("pr_auc_unique_key", None)
            ef1_unique = metrics.get("ef1_unique_key", None)
            bedroc_unique = metrics.get("bedroc_unique_key", None)
            brier_unique = metrics.get("brier_unique_key", None)
            ece_unique = metrics.get("ece_unique_key", None)
            score_unique_ratio = metrics_unique.get("score_unique_ratio", None)
            score_tie_ratio = metrics_unique.get("score_tie_ratio", None)
            score_mode_ratio = metrics_unique.get("score_mode_ratio", None)
            score_orientation_suspect = metrics_unique.get("score_orientation_suspect", None)
            score_orientation_auc_delta = metrics_unique.get("score_orientation_auc_delta", None)

            if isinstance(auc_row, (int, float)):
                gate_summary["ranking_row_auc_aux"] = float(auc_row)
                gate_summary["ranking_auc"] = float(auc_row)  # legacy key

            if isinstance(auc_unique, (int, float)):
                gate_summary["ranking_unique_auc"] = float(auc_unique)
                if (not math.isnan(float(auc_unique))) and float(auc_unique) < float(args.gate_ranking_unique_auc_min):
                    gate_summary["failed_metrics"].append(
                        {
                            "metric": "ranking_unique_auc",
                            "value": float(auc_unique),
                            "threshold": float(args.gate_ranking_unique_auc_min),
                        }
                    )
            else:
                gate_summary["failed_metrics"].append(
                    {
                        "metric": "ranking_unique_auc_present",
                        "value": auc_unique,
                        "threshold": "numeric",
                    }
                )

            if isinstance(auc_ood_unique, (int, float)):
                gate_summary["ranking_ood_unique_auc"] = float(auc_ood_unique)
                if (not math.isnan(float(auc_ood_unique))) and float(auc_ood_unique) < float(args.gate_ranking_ood_auc_min):
                    gate_summary["failed_metrics"].append(
                        {
                            "metric": "ranking_ood_unique_auc",
                            "value": float(auc_ood_unique),
                            "threshold": float(args.gate_ranking_ood_auc_min),
                        }
                    )
            elif bool(args.require_ood_eval):
                gate_summary["failed_metrics"].append(
                    {
                        "metric": "ranking_ood_unique_auc_present",
                        "value": auc_ood_unique,
                        "threshold": "numeric",
                    }
                )

            if isinstance(pr_auc_unique, (int, float)):
                gate_summary["ranking_pr_auc"] = float(pr_auc_unique)
                if (not math.isnan(float(pr_auc_unique))) and float(pr_auc_unique) < float(args.gate_pr_auc_min):
                    gate_summary["failed_metrics"].append(
                        {
                            "metric": "ranking_pr_auc",
                            "value": float(pr_auc_unique),
                            "threshold": float(args.gate_pr_auc_min),
                        }
                    )
            else:
                gate_summary["failed_metrics"].append(
                    {
                        "metric": "ranking_pr_auc_present",
                        "value": pr_auc_unique,
                        "threshold": "numeric",
                    }
                )

            if isinstance(ef1_unique, (int, float)):
                gate_summary["ranking_ef1"] = float(ef1_unique)
                if (not math.isnan(float(ef1_unique))) and float(ef1_unique) < float(args.gate_ef1_min):
                    gate_summary["failed_metrics"].append(
                        {
                            "metric": "ranking_ef1",
                            "value": float(ef1_unique),
                            "threshold": float(args.gate_ef1_min),
                        }
                    )
            else:
                gate_summary["failed_metrics"].append(
                    {
                        "metric": "ranking_ef1_present",
                        "value": ef1_unique,
                        "threshold": "numeric",
                    }
                )

            if isinstance(bedroc_unique, (int, float)):
                gate_summary["ranking_bedroc"] = float(bedroc_unique)
                if (not math.isnan(float(bedroc_unique))) and float(bedroc_unique) < float(args.gate_bedroc_min):
                    gate_summary["failed_metrics"].append(
                        {
                            "metric": "ranking_bedroc",
                            "value": float(bedroc_unique),
                            "threshold": float(args.gate_bedroc_min),
                        }
                    )

            if isinstance(brier_unique, (int, float)):
                gate_summary["ranking_brier"] = float(brier_unique)
                if (not math.isnan(float(brier_unique))) and float(brier_unique) > float(args.gate_brier_max):
                    gate_summary["failed_metrics"].append(
                        {
                            "metric": "ranking_brier",
                            "value": float(brier_unique),
                            "threshold": float(args.gate_brier_max),
                        }
                    )

            if isinstance(ece_unique, (int, float)):
                gate_summary["ranking_ece"] = float(ece_unique)
                if (not math.isnan(float(ece_unique))) and float(ece_unique) > float(args.gate_ece_max):
                    gate_summary["failed_metrics"].append(
                        {
                            "metric": "ranking_ece",
                            "value": float(ece_unique),
                            "threshold": float(args.gate_ece_max),
                        }
                    )

            if isinstance(score_unique_ratio, (int, float)):
                gate_summary["ranking_score_unique_ratio"] = float(score_unique_ratio)
                if float(score_unique_ratio) < float(args.gate_ranking_score_unique_ratio_min):
                    gate_summary["failed_metrics"].append(
                        {
                            "metric": "ranking_score_unique_ratio",
                            "value": float(score_unique_ratio),
                            "threshold": float(args.gate_ranking_score_unique_ratio_min),
                        }
                    )
            elif float(args.gate_ranking_score_unique_ratio_min) > 0:
                gate_summary["failed_metrics"].append(
                    {
                        "metric": "ranking_score_unique_ratio_present",
                        "value": score_unique_ratio,
                        "threshold": "numeric",
                    }
                )

            if isinstance(score_tie_ratio, (int, float)):
                gate_summary["ranking_score_tie_ratio"] = float(score_tie_ratio)
                if float(score_tie_ratio) > float(args.gate_ranking_score_tie_ratio_max):
                    gate_summary["failed_metrics"].append(
                        {
                            "metric": "ranking_score_tie_ratio",
                            "value": float(score_tie_ratio),
                            "threshold": float(args.gate_ranking_score_tie_ratio_max),
                        }
                    )

            if isinstance(score_mode_ratio, (int, float)):
                gate_summary["ranking_score_mode_ratio"] = float(score_mode_ratio)
                if float(score_mode_ratio) > float(args.gate_ranking_score_mode_ratio_max):
                    gate_summary["failed_metrics"].append(
                        {
                            "metric": "ranking_score_mode_ratio",
                            "value": float(score_mode_ratio),
                            "threshold": float(args.gate_ranking_score_mode_ratio_max),
                        }
                    )

            if isinstance(score_orientation_auc_delta, (int, float)):
                gate_summary["ranking_score_orientation_auc_delta"] = float(score_orientation_auc_delta)
            if isinstance(score_orientation_suspect, bool):
                gate_summary["ranking_score_orientation_suspect"] = bool(score_orientation_suspect)
                if bool(score_orientation_suspect) and bool(args.gate_ranking_fail_on_orientation_suspect):
                    gate_summary["failed_metrics"].append(
                        {
                            "metric": "ranking_score_orientation_suspect",
                            "value": bool(score_orientation_suspect),
                            "threshold": False,
                        }
                    )

            roc_ci_low = None
            pr_ci_low = None
            ef1_ci_low = None
            if isinstance(metrics_ci.get("roc_auc_unique_key"), dict):
                roc_ci_low = metrics_ci.get("roc_auc_unique_key", {}).get("low", None)
            if isinstance(metrics_ci.get("pr_auc_unique_key"), dict):
                pr_ci_low = metrics_ci.get("pr_auc_unique_key", {}).get("low", None)
            if isinstance(metrics_ci.get("ef1_unique_key"), dict):
                ef1_ci_low = metrics_ci.get("ef1_unique_key", {}).get("low", None)

            if isinstance(roc_ci_low, (int, float)):
                gate_summary["ranking_roc_auc_ci_low"] = float(roc_ci_low)
                if float(roc_ci_low) < float(args.gate_roc_auc_ci_lower_min):
                    gate_summary["failed_metrics"].append(
                        {
                            "metric": "ranking_roc_auc_ci_low",
                            "value": float(roc_ci_low),
                            "threshold": float(args.gate_roc_auc_ci_lower_min),
                        }
                    )
            elif float(args.gate_roc_auc_ci_lower_min) > 0:
                gate_summary["failed_metrics"].append(
                    {
                        "metric": "ranking_roc_auc_ci_low_present",
                        "value": roc_ci_low,
                        "threshold": "numeric",
                    }
                )
            if isinstance(pr_ci_low, (int, float)):
                gate_summary["ranking_pr_auc_ci_low"] = float(pr_ci_low)
                if float(pr_ci_low) < float(args.gate_pr_auc_ci_lower_min):
                    gate_summary["failed_metrics"].append(
                        {
                            "metric": "ranking_pr_auc_ci_low",
                            "value": float(pr_ci_low),
                            "threshold": float(args.gate_pr_auc_ci_lower_min),
                        }
                    )
            elif float(args.gate_pr_auc_ci_lower_min) > 0:
                gate_summary["failed_metrics"].append(
                    {
                        "metric": "ranking_pr_auc_ci_low_present",
                        "value": pr_ci_low,
                        "threshold": "numeric",
                    }
                )
            if isinstance(ef1_ci_low, (int, float)):
                gate_summary["ranking_ef1_ci_low"] = float(ef1_ci_low)
                if float(ef1_ci_low) < float(args.gate_ef1_ci_lower_min):
                    gate_summary["failed_metrics"].append(
                        {
                            "metric": "ranking_ef1_ci_low",
                            "value": float(ef1_ci_low),
                            "threshold": float(args.gate_ef1_ci_lower_min),
                        }
                    )
            elif float(args.gate_ef1_ci_lower_min) > 0:
                gate_summary["failed_metrics"].append(
                    {
                        "metric": "ranking_ef1_ci_low_present",
                        "value": ef1_ci_low,
                        "threshold": "numeric",
                    }
                )

            topk_k = int(args.gate_topk_k)
            topk_hit = None
            positive_count = None
            positive_count_ood = None
            eval_unique_keys = rank_payload.get("eval_unique_keys", None)
            ood_unique_keys = rank_payload.get("ood_unique_keys", None)
            if isinstance(eval_unique_keys, (int, float)):
                gate_summary["ranking_eval_unique_keys"] = int(float(eval_unique_keys))
            if isinstance(ood_unique_keys, (int, float)):
                gate_summary["ranking_ood_unique_keys"] = int(float(ood_unique_keys))
            if int(args.gate_min_eval_unique_keys) > 0:
                if (not isinstance(eval_unique_keys, (int, float))) or (
                    int(float(eval_unique_keys)) < int(args.gate_min_eval_unique_keys)
                ):
                    gate_summary["failed_metrics"].append(
                        {
                            "metric": "ranking_eval_unique_keys",
                            "value": None if (not isinstance(eval_unique_keys, (int, float))) else int(float(eval_unique_keys)),
                            "threshold": int(args.gate_min_eval_unique_keys),
                        }
                    )
            if int(args.gate_min_ood_unique_keys) > 0:
                if (not isinstance(ood_unique_keys, (int, float))) or (
                    int(float(ood_unique_keys)) < int(args.gate_min_ood_unique_keys)
                ):
                    gate_summary["failed_metrics"].append(
                        {
                            "metric": "ranking_ood_unique_keys",
                            "value": None if (not isinstance(ood_unique_keys, (int, float))) else int(float(ood_unique_keys)),
                            "threshold": int(args.gate_min_ood_unique_keys),
                        }
                    )
            pos_rate = metrics.get("positive_rate_unique_key", None)
            pos_rate_ood = metrics.get("positive_rate_ood_unique_key", None)
            try:
                if isinstance(metrics.get("positive_count_unique_key", None), (int, float)):
                    positive_count = int(float(metrics.get("positive_count_unique_key")))
                elif isinstance(eval_unique_keys, (int, float)) and isinstance(pos_rate, (int, float)):
                    positive_count = int(round(float(eval_unique_keys) * float(pos_rate)))
            except Exception:
                positive_count = None
            try:
                if isinstance(metrics.get("positive_count_ood_unique_key", None), (int, float)):
                    positive_count_ood = int(float(metrics.get("positive_count_ood_unique_key")))
                elif isinstance(ood_unique_keys, (int, float)) and isinstance(pos_rate_ood, (int, float)):
                    positive_count_ood = int(round(float(ood_unique_keys) * float(pos_rate_ood)))
            except Exception:
                positive_count_ood = None
            if positive_count is not None:
                gate_summary["ranking_positive_count"] = int(max(0, positive_count))
            if positive_count_ood is not None:
                gate_summary["ranking_ood_positive_count"] = int(max(0, positive_count_ood))
            if int(args.gate_min_positive_count) > 0:
                max_possible_pos = int(eval_unique_keys) if isinstance(eval_unique_keys, (int, float)) else None
                unattainable_pos = (
                    isinstance(max_possible_pos, int)
                    and int(args.gate_min_positive_count) > int(max_possible_pos)
                )
                if unattainable_pos:
                    gate_summary["warnings"].append(
                        {
                            "metric": "ranking_positive_count",
                            "reason": "threshold_unattainable_with_current_eval_unique_keys",
                            "value": (None if positive_count is None else int(max(0, positive_count))),
                            "threshold": int(args.gate_min_positive_count),
                            "max_possible": int(max_possible_pos),
                        }
                    )
                elif (positive_count is None) or (int(positive_count) < int(args.gate_min_positive_count)):
                    gate_summary["failed_metrics"].append(
                        {
                            "metric": "ranking_positive_count",
                            "value": (None if positive_count is None else int(max(0, positive_count))),
                            "threshold": int(args.gate_min_positive_count),
                        }
                    )
            if int(args.gate_min_ood_positive_count) > 0:
                max_possible_ood_pos = int(ood_unique_keys) if isinstance(ood_unique_keys, (int, float)) else None
                unattainable_ood_pos = (
                    isinstance(max_possible_ood_pos, int)
                    and int(args.gate_min_ood_positive_count) > int(max_possible_ood_pos)
                )
                if unattainable_ood_pos:
                    gate_summary["warnings"].append(
                        {
                            "metric": "ranking_ood_positive_count",
                            "reason": "threshold_unattainable_with_current_ood_unique_keys",
                            "value": (None if positive_count_ood is None else int(max(0, positive_count_ood))),
                            "threshold": int(args.gate_min_ood_positive_count),
                            "max_possible": int(max_possible_ood_pos),
                        }
                    )
                elif (positive_count_ood is None) or (int(positive_count_ood) < int(args.gate_min_ood_positive_count)):
                    gate_summary["failed_metrics"].append(
                        {
                            "metric": "ranking_ood_positive_count",
                            "value": (None if positive_count_ood is None else int(max(0, positive_count_ood))),
                            "threshold": int(args.gate_min_ood_positive_count),
                        }
                    )
            topk_source = topk_unique if len(topk_unique) > 0 else topk
            for rec in topk_source:
                try:
                    if int(rec.get("k", -1)) == topk_k:
                        topk_hit = float(rec.get("hit_rate", 0.0))
                        break
                except Exception:
                    continue
            if (topk_hit is None) and len(topk_source) > 0:
                # gate k가 rows 수보다 큰 경우, 가장 큰 k 레코드를 사용
                try:
                    fallback = sorted(topk_source, key=lambda x: int(x.get("k", -1)))[-1]
                    topk_hit = float(fallback.get("hit_rate", 0.0))
                except Exception:
                    topk_hit = None
            if topk_hit is not None:
                gate_summary["ranking_topk_hit_rate"] = float(topk_hit)
                max_hit_rate = None
                unattainable = False
                if isinstance(positive_count, int):
                    if positive_count <= 0:
                        max_hit_rate = 0.0
                    else:
                        max_hit_rate = float(min(1.0, float(positive_count) / float(max(topk_k, 1))))
                    gate_summary["ranking_topk_hit_rate_max_possible"] = float(max_hit_rate)
                    unattainable = float(args.gate_topk_hit_rate_min) > (float(max_hit_rate) + 1e-12)

                if unattainable:
                    gate_summary["warnings"].append(
                        {
                            "metric": f"topk_hit_rate@{topk_k}",
                            "reason": "threshold_unattainable_with_current_positive_count",
                            "value": float(topk_hit),
                            "threshold": float(args.gate_topk_hit_rate_min),
                            "max_possible": float(max_hit_rate if max_hit_rate is not None else 0.0),
                            "positive_count": int(max(0, positive_count or 0)),
                        }
                    )
                elif topk_hit < float(args.gate_topk_hit_rate_min):
                    gate_summary["failed_metrics"].append(
                        {
                            "metric": f"topk_hit_rate@{topk_k}",
                            "value": float(topk_hit),
                            "threshold": float(args.gate_topk_hit_rate_min),
                        }
                    )

        if gate_max_mean_distance > 0:
            if (gate_mean_d_candidate is None) and (gate_df is not None) and (not gate_df.empty) and ("mean_min_distance_A" in gate_df.columns):
                gate_mean_d_candidate = float(pd.to_numeric(gate_df["mean_min_distance_A"], errors="coerce").mean())
                gate_mean_d_source = "scores_all_mean(fallback)"
            gate_summary["mean_min_distance_A"] = gate_mean_d_candidate
            gate_summary["mean_min_distance_A_source"] = gate_mean_d_source or None
            gate_summary["mean_min_distance_A_topk_k"] = gate_mean_d_topk
            if gate_mean_d_candidate is None:
                gate_summary["failed_metrics"].append(
                    {
                        "metric": "mean_min_distance_A_present",
                        "value": None,
                        "threshold": f"<= {gate_max_mean_distance}",
                    }
                )
            elif float(gate_mean_d_candidate) > gate_max_mean_distance:
                gate_summary["failed_metrics"].append(
                    {
                        "metric": "mean_min_distance_A",
                        "value": float(gate_mean_d_candidate),
                        "threshold": gate_max_mean_distance,
                    }
                )

        gate_summary["pass"] = len(gate_summary["failed_metrics"]) == 0
        if (
            (not bool(gate_summary["pass"]))
            and bool(args.strict_fail_fast)
            and gate_enforcement_mode in {"operational", "both"}
        ):
            payload = {
                "pass": False,
                "failed_stage": "stage6_operational_gate",
                "stages": {
                    "stage_lock": stage_lock,
                    "stage0_leakage_audit": rec0,
                    "stage1_ligand_mapping": rec1,
                "stage1_eval_positive_check": stage1_positive_check,
                "stage2_trajectory_generation": rec_traj,
                "stage2_residual_meta": rec2,
                "stage3_backmapping_scoring": rec3,
                "stage3b_physics_refinement": rec3b,
                "stage4_calibration": rec4,
                "stage45_eval_integrity": rec45,
                "stage5_ranking_eval": rec5,
                "stage6_operational_gate": gate_summary,
            },
                "artifacts": {"summary_json": f"{out_prefix}_summary.json"},
            }
            return _finalize_and_write(out_prefix, payload, args)

    strict_gate_args: argparse.Namespace = args
    if enforce_strict_gate and (not bool(getattr(args, "enforce_strict_gate", False))):
        strict_gate_args = argparse.Namespace(**vars(args))
        strict_gate_args.enforce_strict_gate = True
    strict_gate_summary = _strict_gate_from_operational(gate_summary, strict_gate_args)
    if (
        bool(enforce_strict_gate)
        and (not bool(strict_gate_summary.get("pass", True)))
        and bool(args.strict_fail_fast)
        and gate_enforcement_mode in {"strict", "both"}
    ):
        payload = {
            "pass": False,
            "failed_stage": "stage6_strict_gate",
            "stages": {
                "stage_lock": stage_lock,
                "stage0_leakage_audit": rec0,
                "stage1_ligand_mapping": rec1,
                "stage1_eval_positive_check": stage1_positive_check,
                "stage2_trajectory_generation": rec_traj,
                "stage2_residual_meta": rec2,
                "stage3_backmapping_scoring": rec3,
                "stage3b_physics_refinement": rec3b,
                "stage4_calibration": rec4,
                "stage45_eval_integrity": rec45,
                "stage5_ranking_eval": rec5,
                "stage6_operational_gate": gate_summary,
                "stage6_strict_gate": strict_gate_summary,
            },
            "artifacts": {"summary_json": f"{out_prefix}_summary.json"},
        }
        return _finalize_and_write(out_prefix, payload, args)

    pass_operational = bool(gate_summary.get("pass", True)) if bool(enforce_operational_gate) else True
    pass_strict = bool(strict_gate_summary.get("pass", True)) if bool(enforce_strict_gate) else True
    if gate_enforcement_mode == "strict":
        pipeline_pass = bool(pass_strict)
        pipeline_failed_stage = None if pipeline_pass else "stage6_strict_gate"
    elif gate_enforcement_mode == "both":
        pipeline_pass = bool(pass_operational and pass_strict)
        if not pass_operational:
            pipeline_failed_stage = "stage6_operational_gate"
        elif not pass_strict:
            pipeline_failed_stage = "stage6_strict_gate"
        else:
            pipeline_failed_stage = None
    else:
        pipeline_pass = bool(pass_operational)
        pipeline_failed_stage = None if pipeline_pass else "stage6_operational_gate"

    claim_split_json = str(args.claim_split_json).strip() or f"{out_prefix}_claim_split.json"
    claim_split_md = str(args.claim_split_md).strip() or f"{out_prefix}_claim_split.md"
    claim_split_payload: Dict[str, Any] = {}
    if bool(args.generate_claim_split):
        claim_split_payload = _build_claim_split(gate_summary, rank_payload_for_claim)
        with open(claim_split_json, "w", encoding="utf-8") as f:
            json.dump(claim_split_payload, f, indent=2, ensure_ascii=False)
        claim_lines = [
            "# Ligand Claim Split",
            "",
            f"- pass: {bool(claim_split_payload.get('summary', {}).get('pass', False))}",
            f"- failed_metric_count: {int(claim_split_payload.get('summary', {}).get('failed_metric_count', 0) or 0)}",
            "",
            "## Commercial Claim",
            f"- ranking_unique_auc: {claim_split_payload.get('commercial_claim', {}).get('ranking_unique_auc')}",
            f"- ranking_pr_auc: {claim_split_payload.get('commercial_claim', {}).get('ranking_pr_auc')}",
            f"- ranking_ef1: {claim_split_payload.get('commercial_claim', {}).get('ranking_ef1')}",
            f"- ranking_bedroc: {claim_split_payload.get('commercial_claim', {}).get('ranking_bedroc')}",
            f"- ranking_brier: {claim_split_payload.get('commercial_claim', {}).get('ranking_brier')}",
            f"- ranking_ece: {claim_split_payload.get('commercial_claim', {}).get('ranking_ece')}",
            "",
            "## Research Claim",
            f"- ranking_row_auc_aux: {claim_split_payload.get('research_claim', {}).get('ranking_row_auc_aux')}",
            f"- ranking_score_unique_ratio: {claim_split_payload.get('research_claim', {}).get('ranking_score_unique_ratio')}",
            f"- ranking_score_orientation_auc_delta: {claim_split_payload.get('research_claim', {}).get('ranking_score_orientation_auc_delta')}",
        ]
        with open(claim_split_md, "w", encoding="utf-8") as f:
            f.write("\n".join(claim_lines) + "\n")

    sla_summary_json = str(args.sla_summary_json).strip() or f"{out_prefix}_sla_summary.json"
    sla_summary_md = str(args.sla_summary_md).strip() or f"{out_prefix}_sla_summary.md"
    sla_summary: Dict[str, Any] = _build_sla_summary(
        out_prefix=out_prefix,
        stage0=rec0,
        stage1=rec1,
        stage2_traj=rec_traj,
        stage2_meta=rec2,
        stage3=rec3,
        stage3b=rec3b,
        stage4=rec4,
        stage45=rec45,
        stage5=rec5,
        gate_summary=gate_summary,
        queue_csv=queue_csv,
        trajectory_root=str(generated_trajectory_root),
        heavy_enabled=bool(heavy_paths.get("enabled", False)),
        traj_prod=traj_prod_summary,
        traj_stage2_settings=traj_stage2_settings,
        traj_stage2_diag=traj_stage2_diag,
        traj_stage2_summary_json=f"{stage2_traj_prefix}_summary.json",
        physics_refinement=physics_refinement_runtime,
        physics_refinement_summary_json=stage3b_summary_json if physics_refinement_enabled else "",
    )
    if bool(args.emit_sla_summary):
        with open(sla_summary_json, "w", encoding="utf-8") as f:
            json.dump(sla_summary, f, indent=2, ensure_ascii=False)
        sla_lines = [
            "# Ligand HTVS SLA Summary",
            "",
            f"- pass: {bool(sla_summary.get('pass', False))}",
            f"- total_latency_sec: {sla_summary.get('total_latency_sec')}",
            f"- queue_rows: {sla_summary.get('queue_rows')}",
            f"- queue_rate_stage2_rows_per_sec: {sla_summary.get('queue_rate_stage2_rows_per_sec')}",
            f"- queue_rate_stage3_rows_per_sec: {sla_summary.get('queue_rate_stage3_rows_per_sec')}",
            f"- queue_rate_stage3b_rows_per_sec: {sla_summary.get('queue_rate_stage3b_rows_per_sec')}",
            f"- gate_failed_metric_count: {sla_summary.get('gate_failed_metric_count')}",
            f"- gate_failure_rate_proxy: {sla_summary.get('gate_failure_rate_proxy')}",
            f"- trajectory_root: `{sla_summary.get('trajectory_root')}`",
            f"- heavy_artifacts_enabled: {sla_summary.get('heavy_artifacts_enabled')}",
        ]
        prod_lines = _traj_prod_markdown_lines(
            traj_prod=traj_prod_summary,
            traj_stage2_settings=traj_stage2_settings,
            traj_stage2_diag=traj_stage2_diag,
            heading="## Production Stage2",
        )
        if prod_lines:
            sla_lines.extend(["", *prod_lines])
        refinement_lines = _physics_refinement_markdown_lines(
            physics_refinement_runtime,
            heading="## Physics Refinement",
        )
        if refinement_lines:
            sla_lines.extend(["", *refinement_lines])
        with open(sla_summary_md, "w", encoding="utf-8") as f:
            f.write("\n".join(sla_lines) + "\n")

    stage3_delivery_requested = bool(
        int(max(0, int(args.stage3_delivery_topk_global))) > 0
        or int(max(0, int(args.stage3_delivery_topk_per_target))) > 0
    )
    if bool(pipeline_pass) and stage3_delivery_requested:
        stage3_delivery_prefix = f"{out_prefix}_stage3_delivery_topk"
        stage3_delivery_cmd = [
            sys.executable,
            "tools/run_ligand_topk_delivery.py",
            "--scores-csv",
            stage3_delivery_scores_csv,
            "--queue-csv",
            queue_csv,
            "--trajectory-root",
            str(generated_trajectory_root),
            "--trajectory-glob",
            str(args.trajectory_glob),
            "--out-prefix",
            stage3_delivery_prefix,
            "--score-col",
            str(args.stage3_delivery_score_col),
            "--topk-global",
            str(int(max(0, int(args.stage3_delivery_topk_global)))),
            "--topk-per-target",
            str(int(max(0, int(args.stage3_delivery_topk_per_target)))),
            "--selection-mode",
            str(args.stage3_delivery_selection_mode),
            "--contact-cutoff-A",
            str(float(args.contact_cutoff_A)),
            "--min-frames",
            str(int(args.stage3_min_frames)),
            "--workers",
            str(int(max(0, int(getattr(args, "stage3_delivery_workers", 0) or args.stage3_workers)))),
            "--parallel-threshold",
            str(int(max(1, int(getattr(args, "stage3_parallel_threshold", 2))))),
            "--make-bundle-zip" if bool(args.stage3_delivery_make_bundle_zip) else "--no-make-bundle-zip",
        ]
        rec3_delivery = _run_cmd(stage3_delivery_cmd)

    payload = {
        "pass": bool(pipeline_pass),
        "failed_stage": pipeline_failed_stage,
        "run_scope": mode,
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "gate_enforcement_mode": gate_enforcement_mode,
        "traj_prod": traj_prod_summary,
        "physics_refinement": physics_refinement_runtime,
        "stages": {
            "stage_lock": stage_lock,
            "stage_contract_input": contract_input,
            "stage0_leakage_audit": rec0,
            "stage1_ligand_mapping": rec1,
            "stage1_eval_positive_check": stage1_positive_check,
            "stage2_trajectory_generation": rec_traj,
            "stage2_residual_meta": rec2,
            "stage3_backmapping_scoring": rec3,
            "stage3b_physics_refinement": rec3b,
            "stage4_calibration": rec4,
            "stage45_eval_integrity": rec45,
            "stage5_ranking_eval": rec5,
            "stage5b_admet_surface": rec_admet,
            "stage6_operational_gate": gate_summary,
            "stage6_strict_gate": strict_gate_summary,
            "stage6b_topk_delivery": rec3_delivery,
            "stage8_sla": sla_summary,
        },
        "artifacts": {
            "stage0_leakage_summary_json": f"{out_prefix}_stage0_leakage_summary.json" if bool(args.run_leakage_audit) else "",
            "queue_csv": queue_csv,
            "ligand_json": ligand_json,
            "stage1_summary_json": stage1_summary,
            "trajectory_engine_mode": str(args.trajectory_engine_mode),
            "stage2_trajectory_summary_json": f"{stage2_traj_prefix}_summary.json",
            "trajectory_root": str(generated_trajectory_root),
            "stage2_summary_json": f"{stage2_prefix}_summary.json",
            "stage3_summary_json": f"{stage3_prefix}_summary.json",
            "stage3_scores_csv": stage3_scores_csv,
            "stage3b_physics_refinement_summary_json": stage3b_summary_json if physics_refinement_enabled else "",
            "stage3b_physics_refinement_scores_csv": stage3b_scores_csv if physics_refinement_enabled else "",
            "stage3b_physics_refinement_shortlist_csv": stage3b_shortlist_csv if physics_refinement_enabled else "",
            "stage4_scores_csv": stage4_scores_csv if bool(args.run_calibration) else "",
            "stage4_summary_json": stage4_summary_json if bool(args.run_calibration) else "",
            "stage45_integrity_summary_json": f"{out_prefix}_stage45_integrity_summary.json" if bool(args.enforce_zero_overlap) else "",
            "stage5_summary_json": stage5_summary_json if bool(args.run_ranking_eval) else "",
            "admet_surface_json": admet_surface_json,
            "stage3_delivery_summary_json": (
                f"{out_prefix}_stage3_delivery_topk_summary.json"
                if stage3_delivery_requested
                else ""
            ),
            "stage3_delivery_selection_mode": str(args.stage3_delivery_selection_mode),
            "claim_split_json": claim_split_json if bool(args.generate_claim_split) else "",
            "claim_split_md": claim_split_md if bool(args.generate_claim_split) else "",
            "sla_summary_json": sla_summary_json if bool(args.emit_sla_summary) else "",
            "sla_summary_md": sla_summary_md if bool(args.emit_sla_summary) else "",
            "physics_refinement_enabled": bool(physics_refinement_runtime.get("enabled", False)),
            "physics_refinement_downstream_scores_csv": str(physics_refinement_runtime.get("downstream_scores_csv", "") or ""),
            "physics_refinement_calibration_proxy_col_used": str(physics_refinement_runtime.get("calibration_proxy_col_used", "") or ""),
            "scored_csv_final": scored_csv_for_gate,
            "gate_enforcement_mode": gate_enforcement_mode,
            "heavy_artifacts_enabled": bool(heavy_paths.get("enabled", False)),
            "heavy_artifacts_root": str(heavy_paths.get("root", "")),
            "heavy_run_dir": str(heavy_paths.get("run_dir", "")),
            "summary_json": f"{out_prefix}_summary.json",
            "summary_md": f"{out_prefix}_summary.md",
        },
    }
    contract_output = {"ok": True, "skipped": True, "errors": [], "warnings": []}
    if bool(args.enforce_data_contract):
        contract_output = _validate_data_contract_output(payload, str(args.data_contract_json))
        contract_output["skipped"] = False
    payload["stages"]["stage7_data_contract_output"] = contract_output
    if bool(args.enforce_data_contract) and (not bool(contract_output.get("ok", False))):
        payload["pass"] = False
        payload["failed_stage"] = "stage7_data_contract_output"
    payload = _finalize_and_write(out_prefix, payload, args)
    md_lines = [
        "# Ligand HTVS Pipeline",
        "",
        f"- generated_at_local: {payload['generated_at_local']}",
        f"- pass: {payload['pass']}",
        f"- run_scope: {mode}",
        f"- summary_json_abs: `{payload.get('path_info', {}).get('summary_json_abs', '')}`",
        f"- summary_md_abs: `{payload.get('path_info', {}).get('summary_md_abs', '')}`",
        "",
        "## Artifacts",
        f"- queue_csv: `{queue_csv}`",
        f"- stage0_leakage_summary_json: `{payload['artifacts']['stage0_leakage_summary_json']}`",
        f"- trajectory_engine_mode: `{str(args.trajectory_engine_mode)}`",
        f"- trajectory_root: `{generated_trajectory_root}`",
        f"- stage2_trajectory_summary_json: `{stage2_traj_prefix}_summary.json`",
        f"- stage2_summary_json: `{stage2_prefix}_summary.json`",
        f"- stage3_summary_json: `{stage3_prefix}_summary.json`",
        f"- stage3_scores_csv: `{stage3_prefix}_scores.csv`",
        f"- stage3b_physics_refinement_summary_json: `{payload['artifacts']['stage3b_physics_refinement_summary_json']}`",
        f"- stage3b_physics_refinement_scores_csv: `{payload['artifacts']['stage3b_physics_refinement_scores_csv']}`",
        f"- stage3b_physics_refinement_shortlist_csv: `{payload['artifacts']['stage3b_physics_refinement_shortlist_csv']}`",
        f"- stage4_summary_json: `{payload['artifacts']['stage4_summary_json']}`",
        f"- stage45_integrity_summary_json: `{payload['artifacts']['stage45_integrity_summary_json']}`",
        f"- stage5_summary_json: `{payload['artifacts']['stage5_summary_json']}`",
        f"- stage3_delivery_summary_json: `{payload['artifacts']['stage3_delivery_summary_json']}`",
        f"- claim_split_json: `{payload['artifacts']['claim_split_json']}`",
        f"- sla_summary_json: `{payload['artifacts']['sla_summary_json']}`",
        f"- sla_summary_md: `{payload['artifacts']['sla_summary_md']}`",
        f"- heavy_artifacts_enabled: `{payload['artifacts']['heavy_artifacts_enabled']}`",
        f"- heavy_artifacts_root: `{payload['artifacts']['heavy_artifacts_root']}`",
        f"- heavy_run_dir: `{payload['artifacts']['heavy_run_dir']}`",
        f"- physics_refinement_enabled: `{payload['artifacts']['physics_refinement_enabled']}`",
        f"- physics_refinement_downstream_scores_csv: `{payload['artifacts']['physics_refinement_downstream_scores_csv']}`",
        f"- physics_refinement_calibration_proxy_col_used: `{payload['artifacts']['physics_refinement_calibration_proxy_col_used']}`",
        f"- scored_csv_final: `{payload['artifacts']['scored_csv_final']}`",
        f"- gate_enforcement_mode: `{gate_enforcement_mode}`",
        f"- stage6_operational_gate_pass: `{gate_summary.get('pass')}`",
        f"- stage6_strict_gate_pass: `{strict_gate_summary.get('pass')}`",
        f"- stage7_data_contract_output_ok: `{contract_output.get('ok')}`",
    ]
    prod_lines = _traj_prod_markdown_lines(
        traj_prod=traj_prod_summary,
        traj_stage2_settings=traj_stage2_settings,
        traj_stage2_diag=traj_stage2_diag,
        heading="## Production Stage2",
    )
    if prod_lines:
        md_lines.extend(["", *prod_lines])
    refinement_lines = _physics_refinement_markdown_lines(
        physics_refinement_runtime,
        heading="## Physics Refinement",
    )
    if refinement_lines:
        md_lines.extend(["", *refinement_lines])
    with open(f"{out_prefix}_summary.md", "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")
    return payload


def build_parser() -> argparse.ArgumentParser:
    stamp = dt.date.today().isoformat()
    p = argparse.ArgumentParser(
        description=(
            "Run ligand HTVS pipeline "
            "(mapping -> residual/meta -> trajectory/scoring -> optional physics refinement -> calibration -> ranking -> gate)."
        )
    )
    p.add_argument("--date-tag", type=str, default="")
    p.add_argument("--run-scope", type=str, default="smoke", choices=["smoke", "full", "smoke_then_full"])
    p.add_argument("--targets", type=str, default="KRAS_G12D,EGFR_KINASE,HIV1_PROTEASE")
    p.add_argument("--out-prefix", type=str, default=f"runs/ligand_htvs_pipeline_{stamp}")
    p.add_argument("--single-instance", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--lock-file", type=str, default="")
    p.add_argument("--resume-stage3-only", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--enforce-data-contract", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--data-contract-json", type=str, default="config/ligand_data_contract_v1.json")
    p.add_argument("--service-error-codes-json", type=str, default="config/ligand_service_error_codes_v1.json")
    p.add_argument("--service-schema-version", type=str, default="ligand_service_result_v1")
    p.add_argument("--service-retry-after-sec-default", type=int, default=300)
    p.add_argument("--service-retry-after-sec-transient", type=int, default=60)
    p.add_argument("--generate-claim-split", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--claim-split-json", type=str, default="")
    p.add_argument("--claim-split-md", type=str, default="")
    p.add_argument("--emit-sla-summary", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--sla-summary-json", type=str, default="")
    p.add_argument("--sla-summary-md", type=str, default="")
    p.add_argument("--heavy-artifacts-root", type=str, default="")
    p.add_argument("--heavy-artifacts-subdir", type=str, default="")
    p.add_argument("--auto-heavy-artifacts-root", action=argparse.BooleanOptionalAction, default=False)

    p.add_argument("--ligand-sdf", type=str, default="")
    p.add_argument("--ligand-csv", type=str, default="config/ligand_smoke_seed_v1.csv")
    p.add_argument("--target-pocket-csv", type=str, default="")
    p.add_argument("--target-native-csv", type=str, default="config/real_drug_targets_native_v1.csv")
    p.add_argument("--require-native-path", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--queue-policy", type=str, default="round_robin", choices=["round_robin", "target_block", "random"])
    p.add_argument("--stage1-csv-prioritize-binders", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--stage1-csv-binder-col", type=str, default="is_binder")
    p.add_argument("--stage1-min-eval-positive-keys", type=int, default=0)
    p.add_argument("--stage1-min-eval-positive-3d-ready-keys", type=int, default=0)
    p.add_argument("--stage1-require-positive-3d-ready", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument(
        "--stage1-require-native-path-for-positive-check",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    p.add_argument("--stage1-positive-check-labels-csv", type=str, default="")
    p.add_argument("--stage1-positive-check-split-csv", type=str, default="")
    p.add_argument("--stage1-positive-check-eval-roles", type=str, default="")
    p.add_argument("--stage1-positive-check-role-col", type=str, default="role")
    p.add_argument("--stage1-positive-check-target-col", type=str, default="target")
    p.add_argument("--stage1-positive-check-ligand-col", type=str, default="ligand_id")
    p.add_argument("--stage1-positive-check-binder-col", type=str, default="is_binder")
    p.add_argument("--csv-relax-3d", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--csv-relax-max-iters", type=int, default=200)
    p.add_argument("--csv-relax-embed-seed", type=int, default=13)
    p.add_argument("--csv-relax-workers", type=int, default=0)
    p.add_argument("--csv-smiles-cache-json", type=str, default="runs/ligand_smiles_bead_cache.json")
    p.add_argument(
        "--reuse-stage1-if-exists",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Reuse existing stage1 queue/ligand artifacts if present and non-empty.",
    )
    p.add_argument("--replicas-smoke", type=int, default=6)
    p.add_argument("--replicas-full", type=int, default=640)
    p.add_argument("--max-ligands-smoke", type=int, default=6)
    p.add_argument("--max-ligands-full", type=int, default=640)
    p.add_argument("--jobs-per-target-smoke", type=int, default=6)
    p.add_argument("--jobs-per-target-full", type=int, default=640)

    p.add_argument("--priority-topk", type=int, default=4)
    p.add_argument("--priority-bonus", type=float, default=1.5)
    p.add_argument("--hard-mining-topk", type=int, default=4)
    p.add_argument("--curriculum-base-manifest-csv", type=str, default="runs/distilled_residual_manifest_repaired_fp32_cap100.csv")
    p.add_argument("--curriculum-max-targets", type=int, default=0)
    p.add_argument("--curriculum-checkpoint-dir", type=str, default="models/curriculum_ligand_active")
    p.add_argument("--curriculum-out-json", type=str, default=f"runs/bigdata_curriculum_ligand_active_{stamp}.json")
    p.add_argument("--curriculum-summary-json", type=str, default=f"runs/train_curriculum_ligand_active_{stamp}.json")
    p.add_argument("--curriculum-summary-csv", type=str, default=f"runs/train_curriculum_ligand_active_{stamp}.csv")
    p.add_argument("--skip-curriculum-training", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--skip-claim-correction", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--accuracy-external-csv", type=str, default="")
    p.add_argument("--stage2-csv", type=str, default="")
    p.add_argument("--claim-policy-json", type=str, default="config/allatom_equivalence_acceptance_v1_2026-02-17.json")
    p.add_argument("--claim-strict-summary-json", type=str, default="")
    p.add_argument("--claim-accuracy-external-csv", type=str, default="")
    p.add_argument("--claim-thermo-input-csv", type=str, default="")
    p.add_argument("--claim-kinetics-input-csv", type=str, default="")
    p.add_argument("--claim-out-prefix", type=str, default=f"runs/claim_metric_correction_loop_ligand_active_{stamp}")

    p.add_argument("--run-trajectory-sim", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--trajectory-engine-mode", type=str, default="rust_hip", choices=["proxy", "rust_hip"])
    p.add_argument("--traj-frames-smoke", type=int, default=120)
    p.add_argument("--traj-frames-full", type=int, default=300)
    p.add_argument("--traj-write-every", type=int, default=1)
    p.add_argument(
        "--traj-frame-output-format",
        type=str,
        default="pdb_files",
        choices=["pdb_files", "npz_bundle"],
    )
    p.add_argument(
        "--traj-auto-fast-output",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "When stage3 is score-only and no delivery artifacts are requested, "
            "automatically switch stage2 output from pdb_files to npz_bundle."
        ),
    )
    p.add_argument("--traj-npz-compression", type=str, default="store", choices=["store", "compressed"])
    p.add_argument("--traj-npz-layout", type=str, default="flat_shard", choices=["job_dir", "flat_root", "flat_shard"])
    p.add_argument("--traj-npz-shard-size", type=int, default=512)
    p.add_argument("--traj-engine-cache-max-entries", type=int, default=16)
    p.add_argument("--traj-job-batch-size", type=int, default=0)
    p.add_argument("--traj-job-batch-autotune-candidates", type=str, default="1,2,4,8")
    p.add_argument("--traj-job-batch-autotune-frames", type=int, default=12)
    p.add_argument("--traj-writer-workers", type=int, default=1)
    p.add_argument("--traj-writer-mode", type=str, default="process", choices=["sync", "thread", "process"])
    p.add_argument("--traj-writer-max-pending", type=int, default=64)
    p.add_argument(
        "--traj-prod-stage2-preset",
        type=str,
        default="off",
        choices=["off", "auto", "default", "gpcr", "ion_trpv1", "kinase_protease"],
        help=(
            "Production-only stage2 preset selector. `auto` infers target family from the configured targets; "
            "`off` preserves the current generic stage2 settings."
        ),
    )
    p.add_argument("--traj-prod-stage2-preset-strict", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--traj-prod-profile-intent", type=str, default="")
    p.add_argument("--traj-prod-speedpack", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--traj-prod-adaptive-frame-budget", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--traj-prod-frame-budget-tiers", type=str, default="0.90:1.00,0.75:0.85,0.60:0.70,0.00:0.55")
    p.add_argument("--traj-prod-min-frames-smoke", type=int, default=80)
    p.add_argument("--traj-prod-min-frames-full", type=int, default=160)
    p.add_argument("--traj-prod-early-stop-enabled", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--traj-prod-early-stop-min-frames-smoke", type=int, default=80)
    p.add_argument("--traj-prod-early-stop-min-frames-full", type=int, default=160)
    p.add_argument("--traj-prod-early-stop-window", type=int, default=12)
    p.add_argument("--traj-prod-early-stop-contact-drift", type=float, default=0.015)
    p.add_argument("--traj-prod-early-stop-min-distance-drift-A", type=float, default=0.12)
    p.add_argument("--traj-prod-early-stop-max-mean-min-distance-A", type=float, default=6.0)
    p.add_argument(
        "--traj-prod-light-artifacts",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "When production speedpack is enabled, ask the trajectory engine to skip non-essential "
            "stage2 artifacts such as target tail CSVs, manifest chunks, and markdown summaries."
        ),
    )
    p.add_argument("--traj-prod-light-progress-every-jobs", type=int, default=250)
    p.add_argument("--traj-seed", type=int, default=7)
    p.add_argument("--traj-step-size", type=float, default=0.04)
    p.add_argument("--traj-noise-scale", type=float, default=0.15)
    p.add_argument("--traj-pocket-attract-base", type=float, default=0.16)
    p.add_argument("--traj-protein-repulse", type=float, default=0.22)
    p.add_argument("--traj-bond-k", type=float, default=0.25)
    p.add_argument("--traj-repulse-cutoff-A", type=float, default=4.5)
    p.add_argument("--traj-max-pocket-radius-A", type=float, default=12.0)
    p.add_argument("--traj-dt-fs", type=float, default=0.002)
    p.add_argument("--traj-friction", type=float, default=1.0)
    p.add_argument("--traj-kT", type=float, default=(0.001987 * 300.0))
    p.add_argument("--traj-force-clip", type=float, default=200.0)
    p.add_argument("--traj-box-size-A", type=float, default=120.0)
    p.add_argument("--traj-ff-sigma", type=float, default=3.8)
    p.add_argument("--traj-ff-eps-solv", type=float, default=25.0)
    p.add_argument("--traj-force-backend", type=str, default="auto", choices=["auto", "pytorch"])
    p.add_argument("--traj-require-rust-hip", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument(
        "--traj-strategy-mode",
        type=str,
        default="dynamic",
        choices=["dynamic", "core_only", "adress_only"],
        help="Strategy mode for rust_hip trajectory engine.",
    )
    p.add_argument("--traj-dynamic-adress-min-affinity", type=float, default=0.78)
    p.add_argument("--traj-dynamic-adress-max-protein-residues", type=int, default=200)
    p.add_argument("--traj-dynamic-adress-min-ligand-mw", type=float, default=250.0)
    p.add_argument("--traj-dynamic-adress-fraction", type=float, default=0.15)
    p.add_argument("--traj-dynamic-adress-base-radius-A", type=float, default=6.0)
    p.add_argument("--traj-dynamic-adress-affinity-radius-scale", type=float, default=3.0)
    p.add_argument("--traj-dynamic-adress-mw-radius-scale", type=float, default=2.5)
    p.add_argument("--traj-dynamic-adress-max-all-atom-radius-A", type=float, default=8.0)
    p.add_argument("--traj-dynamic-adress-max-atom-ratio", type=float, default=0.10)
    p.add_argument(
        "--traj-dynamic-adress-cap-force-core-on-radius",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    p.add_argument("--traj-dynamic-adress-force-targets", type=str, default="")
    p.add_argument(
        "--traj-dynamic-core-fallback-on-oom",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    p.add_argument("--traj-abort-on-runtime-error", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--traj-abort-on-cpu-backend", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--native-path-col", type=str, default="native_pdb_path")

    p.add_argument("--trajectory-root", type=str, default="")
    p.add_argument("--trajectory-glob", type=str, default="")
    p.add_argument("--allow-missing-trajectory", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--stage3-min-frames", type=int, default=100)
    p.add_argument("--stage3-workers", type=int, default=0)
    p.add_argument("--stage3-parallel-threshold", type=int, default=2)
    p.add_argument("--stage3-score-only", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--stage3-aux-model-checkpoint", type=str, default="")
    p.add_argument("--stage3-aux-score-weight", type=float, default=0.35)
    p.add_argument("--stage3-residual-prototype-enabled", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--stage3-residual-prototype-mode", type=str, default="shadow_only")
    p.add_argument("--stage3-residual-prototype-family", type=str, default="")
    p.add_argument("--stage3-residual-prototype-spec-json", type=str, default="")
    p.add_argument(
        "--stage3-residual-prototype-runtime-hook-ready",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    p.add_argument("--stage3-residual-prototype-max-abs-delta-score", type=float, default=None)
    p.add_argument("--stage3-residual-prototype-yellow-band-abs-delta-score", type=float, default=None)
    p.add_argument("--stage3-score-reference-scaling-mode", type=str, default="run_local")
    p.add_argument("--stage3-score-reference-stats-json", type=str, default="")
    p.add_argument("--run-physics-refinement", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--physics-refinement-mode", type=str, default="explicit_water_surrogate")
    p.add_argument("--physics-refinement-backend", type=str, default="deterministic_surrogate_wrapper_v1")
    p.add_argument("--physics-refinement-score-col", type=str, default="")
    p.add_argument("--physics-refinement-topk-global", type=int, default=32)
    p.add_argument("--physics-refinement-topk-per-target", type=int, default=0)
    p.add_argument("--physics-refinement-selection-mode", type=str, default="union", choices=["union", "intersection"])
    p.add_argument("--physics-refinement-use-refined-scores-downstream", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--physics-refinement-use-refined-proxy-for-calibration", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument(
        "--physics-refinement-refined-energy-col",
        type=str,
        default="binding_energy_explicit_water_recheck_kcal_mol_proxy",
    )
    p.add_argument("--physics-refinement-refined-rank-col", type=str, default="binding_score_stronger_physics_v1")
    p.add_argument("--stage3-delivery-topk-global", type=int, default=0)
    p.add_argument("--stage3-delivery-topk-per-target", type=int, default=0)
    p.add_argument("--stage3-delivery-score-col", type=str, default="")
    p.add_argument("--stage3-delivery-selection-mode", type=str, default="union")
    p.add_argument("--stage3-delivery-workers", type=int, default=0)
    p.add_argument("--stage3-delivery-make-bundle-zip", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--contact-cutoff-A", type=float, default=6.0)
    p.add_argument("--max-jobs-score-smoke", type=int, default=18)
    p.add_argument("--max-jobs-score-full", type=int, default=640)
    p.add_argument("--make-bundle-zip", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--run-calibration", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--calibration-reference-csv", type=str, default="config/ligand_binding_reference_expanded_v2.csv")
    p.add_argument("--calibration-proxy-col", type=str, default="binding_energy_mmpbsa_kcal_mol_proxy")
    p.add_argument("--calibration-reference-value-col", type=str, default="reference_binding_kcal_mol")
    p.add_argument("--eval-split-csv", type=str, default="")
    p.add_argument("--calibration-fit-roles", type=str, default="fit")
    p.add_argument("--require-split-for-calibration", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--calibration-min-pairs-to-fit", type=int, default=3)
    p.add_argument("--calibration-min-fit-unique-keys", type=int, default=0)
    p.add_argument("--calibration-clip-abs", type=float, default=200.0)
    p.add_argument("--calibration-out-col", type=str, default="binding_energy_mmpbsa_kcal_mol_calibrated")
    p.add_argument("--run-ranking-eval", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--ranking-labels-csv", type=str, default="config/ligand_binding_reference_expanded_v2.csv")
    p.add_argument("--ranking-score-col", type=str, default="binding_energy_mmpbsa_kcal_mol_calibrated")
    p.add_argument("--ranking-probability-score-col", type=str, default="")
    p.add_argument("--ranking-binder-col", type=str, default="is_binder")
    p.add_argument("--ranking-ref-energy-col", type=str, default="reference_binding_kcal_mol")
    p.add_argument("--ranking-eval-roles", type=str, default="eval")
    p.add_argument("--ranking-ood-eval-roles", type=str, default="ood_eval")
    p.add_argument("--require-split-for-ranking", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--require-ood-eval", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--ranking-min-expected-score-coverage", type=float, default=0.0)
    p.add_argument("--ranking-binder-threshold-kcal-mol", type=float, default=-3.0)
    p.add_argument("--ranking-topk-list", type=str, default="10,20,50")
    p.add_argument("--enforce-zero-overlap", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--stage45-min-observed-fit-coverage-ratio", type=float, default=0.0)
    p.add_argument("--stage45-min-observed-eval-coverage-ratio", type=float, default=0.0)
    p.add_argument("--stage45-min-observed-eval-positive-coverage-ratio", type=float, default=0.0)
    p.add_argument("--run-leakage-audit", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--leakage-fit-roles", type=str, default="fit")
    p.add_argument("--leakage-eval-roles", type=str, default="")
    p.add_argument("--leakage-target-meta-csv", type=str, default="")
    p.add_argument("--leakage-ligand-meta-csv", type=str, default="")
    p.add_argument("--leakage-max-key-overlap", type=int, default=0)
    p.add_argument("--leakage-max-target-overlap", type=int, default=0)
    p.add_argument("--leakage-max-family-overlap-ratio", type=float, default=0.0)
    p.add_argument("--leakage-max-scaffold-overlap-ratio", type=float, default=0.0)
    p.add_argument("--leakage-max-allowed-seq-identity", type=float, default=0.30)
    p.add_argument("--leakage-max-allowed-pocket-jaccard", type=float, default=0.40)
    p.add_argument("--enforce-operational-gate", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--enforce-strict-gate", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--gate-enforcement-mode", type=str, default="operational", choices=["operational", "strict", "both"])
    p.add_argument("--strict-fail-fast", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--gate-min-frames", type=int, default=100)
    p.add_argument("--gate-max-mean-min-distance-A", type=float, default=2.5)
    p.add_argument("--gate-distance-override-csv", type=str, default="")
    p.add_argument(
        "--gate-mean-min-distance-source",
        type=str,
        default="eval_unique_topk",
        choices=["scores_all_mean", "eval_unique_mean", "eval_unique_topk"],
    )
    p.add_argument("--gate-mean-min-distance-topk", type=int, default=200)
    p.add_argument("--gate-ranking-auc-min", type=float, default=0.90)
    p.add_argument("--gate-ranking-unique-auc-min", type=float, default=0.90)
    p.add_argument("--gate-ranking-ood-auc-min", type=float, default=0.85)
    p.add_argument("--gate-pr-auc-min", type=float, default=0.60)
    p.add_argument("--gate-ef1-min", type=float, default=1.25)
    p.add_argument("--gate-bedroc-min", type=float, default=0.30)
    p.add_argument("--gate-brier-max", type=float, default=0.30)
    p.add_argument("--gate-ece-max", type=float, default=0.30)
    p.add_argument("--gate-roc-auc-ci-lower-min", type=float, default=0.80)
    p.add_argument("--gate-pr-auc-ci-lower-min", type=float, default=0.50)
    p.add_argument("--gate-ef1-ci-lower-min", type=float, default=1.00)
    p.add_argument("--gate-topk-k", type=int, default=10)
    p.add_argument("--gate-topk-hit-rate-min", type=float, default=0.80)
    p.add_argument("--gate-min-positive-count", type=int, default=0)
    p.add_argument("--gate-min-ood-positive-count", type=int, default=0)
    p.add_argument("--gate-min-eval-unique-keys", type=int, default=0)
    p.add_argument("--gate-min-ood-unique-keys", type=int, default=0)
    p.add_argument("--gate-ranking-min-expected-score-coverage", type=float, default=0.0)
    p.add_argument("--gate-ranking-score-unique-ratio-min", type=float, default=0.0)
    p.add_argument("--gate-ranking-score-tie-ratio-max", type=float, default=1.0)
    p.add_argument("--gate-ranking-score-mode-ratio-max", type=float, default=1.0)
    p.add_argument("--gate-ranking-fail-on-orientation-suspect", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--strict-gate-min-frames", type=int, default=100)
    p.add_argument("--strict-gate-max-mean-min-distance-A", type=float, default=2.5)
    p.add_argument("--strict-gate-ranking-unique-auc-min", type=float, default=0.90)
    p.add_argument("--strict-gate-ranking-ood-auc-min", type=float, default=0.85)
    p.add_argument("--strict-gate-pr-auc-min", type=float, default=0.60)
    p.add_argument("--strict-gate-ef1-min", type=float, default=1.25)
    p.add_argument("--strict-gate-bedroc-min", type=float, default=0.30)
    p.add_argument("--strict-gate-brier-max", type=float, default=0.30)
    p.add_argument("--strict-gate-ece-max", type=float, default=0.30)
    p.add_argument("--strict-gate-roc-auc-ci-lower-min", type=float, default=0.80)
    p.add_argument("--strict-gate-pr-auc-ci-lower-min", type=float, default=0.50)
    p.add_argument("--strict-gate-ef1-ci-lower-min", type=float, default=1.00)
    p.add_argument("--strict-gate-topk-hit-rate-min", type=float, default=0.80)
    p.add_argument("--strict-gate-min-positive-count", type=int, default=0)
    p.add_argument("--strict-gate-min-ood-positive-count", type=int, default=0)
    p.add_argument("--strict-gate-ranking-min-expected-score-coverage", type=float, default=0.0)
    p.add_argument("--strict-gate-score-unique-ratio-min", type=float, default=0.0)
    p.add_argument("--strict-gate-score-tie-ratio-max", type=float, default=1.0)
    p.add_argument("--strict-gate-score-mode-ratio-max", type=float, default=1.0)
    p.add_argument("--strict-gate-fail-on-orientation-suspect", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--ranking-bootstrap-n", type=int, default=400)
    p.add_argument("--ranking-bootstrap-seed", type=int, default=7)
    p.add_argument("--ranking-bootstrap-bedroc-alpha", type=float, default=20.0)
    p.add_argument("--ranking-ece-bins", type=int, default=10)
    p.add_argument("--ranking-probability-logit-scale", type=float, default=1.35)
    p.add_argument("--ranking-labels-driven-eval", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--ranking-missing-score-policy", type=str, default="worst", choices=["worst", "drop"])
    p.add_argument("--ranking-missing-score-worst-margin", type=float, default=1000.0)
    p.add_argument("--ranking-missing-score-worst-value", type=float, default=None)
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = run_pipeline(args)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if bool(args.strict_fail_fast) and (not bool(payload.get("pass", False))):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
