#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import multiprocessing as mp
import os
import re
import shutil
import signal
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
import urllib.parse
import fcntl
import sys
import random
import hashlib
import subprocess
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd
import torch

from core.config import config as core_config
from core.definitions import ResearchConstants
from tools.build_distilled_residual_dataset import build_distilled_residual_dataset
from tools.fetch_public_structure_set import fetch_public_structure_set
from tools.generate_perturbed_data import DataGenerator
from train.train_pipeline import run_training_pipeline

DEFAULT_AFDB_UNIPROT_QUERY = "reviewed:true AND organism_id:9606 AND annotation_score:5"
UNIPROT_QUERY_MAX_SIZE = 500


def _now_local() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _normalize_key(value: str) -> str:
    return "".join(ch for ch in str(value).strip().lower() if ch.isalnum())


def _slug(value: str) -> str:
    out: List[str] = []
    prev_us = False
    for ch in str(value).strip().lower():
        if ch.isalnum():
            out.append(ch)
            prev_us = False
            continue
        if not prev_us:
            out.append("_")
            prev_us = True
    s = "".join(out).strip("_")
    return s or "target"


def _compose_protein_id(target: str, pdb_id: str, uniprot_id: str) -> str:
    u = str(uniprot_id).strip().upper()
    p = str(pdb_id).strip().upper()
    t = _normalize_key(target)
    if u:
        return f"U:{u}"
    if p:
        return f"P:{p}"
    return f"T:{t or 'unknown'}"


def _runtime_target_name(row: Dict[str, Any]) -> str:
    target_raw = str(row.get("target", "")).strip()
    base = target_raw if target_raw else str(row.get("protein_id", "target"))
    slug = _slug(base)
    return f"Live_{slug}"


def _refresh_csv_from_url(url: str, out_csv: str, timeout_sec: float) -> Dict[str, Any]:
    if not str(url).strip():
        return {"refreshed": False, "url": "", "out_csv": out_csv}
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".dl_", suffix=".csv", dir=os.path.dirname(out_csv) or ".")
    os.close(fd)
    try:
        with urllib.request.urlopen(str(url).strip(), timeout=float(timeout_sec)) as resp:
            payload = resp.read()
        with open(tmp, "wb") as f:
            f.write(payload)
        pd.read_csv(tmp)  # validate csv parse
        os.replace(tmp, out_csv)
        return {
            "refreshed": True,
            "url": str(url).strip(),
            "out_csv": os.path.abspath(out_csv),
            "bytes": int(len(payload)),
        }
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _download_text(url: str, timeout_sec: float) -> str:
    req = urllib.request.Request(
        url=str(url).strip(),
        headers={"User-Agent": "md-live-learning-bot/1.0"},
    )
    with urllib.request.urlopen(req, timeout=float(timeout_sec)) as resp:
        payload = resp.read()
    return payload.decode("utf-8", errors="ignore")


def _download_json(url: str, timeout_sec: float) -> Any:
    raw = _download_text(url=url, timeout_sec=timeout_sec)
    return json.loads(raw)


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return float(default)
        s = str(v).strip()
        if (not s) or s.lower() == "nan":
            return float(default)
        return float(s)
    except Exception:
        return float(default)


def _clean_str(v: Any) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    if (not s) or s.lower() == "nan":
        return ""
    return s


def _normalize_source_columns(df: pd.DataFrame) -> pd.DataFrame:
    wanted = ["target", "pdb_id", "uniprot_id", "priority", "pdb_url", "afdb_url", "notes"]
    out = df.copy()
    for col in wanted:
        if col not in out.columns:
            out[col] = ""
    out["target"] = out["target"].map(_clean_str)
    out["pdb_id"] = out["pdb_id"].map(_clean_str).str.upper()
    out["uniprot_id"] = out["uniprot_id"].map(_clean_str).str.upper()
    out["priority"] = out["priority"].map(lambda x: _safe_float(x, 0.0))
    out["pdb_url"] = out["pdb_url"].map(_clean_str)
    out["afdb_url"] = out["afdb_url"].map(_clean_str)
    out["notes"] = out["notes"].map(_clean_str)
    return out[wanted]


def _normalize_md_source_columns(df: pd.DataFrame) -> pd.DataFrame:
    wanted = ["target", "pdb_id", "uniprot_id", "md_url", "md_path", "label", "notes"]
    out = df.copy()
    for col in wanted:
        if col not in out.columns:
            out[col] = ""
    out["target"] = out["target"].map(_clean_str)
    out["pdb_id"] = out["pdb_id"].map(_clean_str).str.upper()
    out["uniprot_id"] = out["uniprot_id"].map(_clean_str).str.upper()
    out["md_url"] = out["md_url"].map(_clean_str)
    out["md_path"] = out["md_path"].map(_clean_str)
    out["label"] = out["label"].map(_clean_str)
    out["notes"] = out["notes"].map(_clean_str)
    return out[wanted]


def _compose_protein_id_from_row(row: Dict[str, Any]) -> str:
    return _compose_protein_id(
        target=str(row.get("target", "")),
        pdb_id=str(row.get("pdb_id", "")),
        uniprot_id=str(row.get("uniprot_id", "")),
    )


def _parse_float_grid(raw: str, default: Sequence[float]) -> List[float]:
    vals: List[float] = []
    for tok in str(raw or "").split(","):
        t = tok.strip()
        if not t:
            continue
        try:
            vals.append(float(t))
        except Exception:
            continue
    if vals:
        return vals
    return [float(x) for x in default]


def _parse_int_grid(raw: str, default: Sequence[int]) -> List[int]:
    vals: List[int] = []
    for tok in str(raw or "").split(","):
        t = tok.strip()
        if not t:
            continue
        try:
            vals.append(int(float(t)))
        except Exception:
            continue
    if vals:
        return vals
    return [int(x) for x in default]


def _resolve_env_perturb_grids(args: argparse.Namespace) -> Dict[str, List[float]]:
    return {
        "temp": _parse_float_grid(str(getattr(args, "env_perturb_temp_grid", "")), [280.0, 300.0, 330.0, 360.0, 420.0]),
        "salt_conc": _parse_float_grid(str(getattr(args, "env_perturb_salt_conc_grid", "")), [0.05, 0.10, 0.20, 0.30]),
        "pH": _parse_float_grid(str(getattr(args, "env_perturb_ph_grid", "")), [6.5, 7.0, 7.4, 8.0]),
        "ionic_strength": _parse_float_grid(str(getattr(args, "env_perturb_ionic_strength_grid", "")), [0.05, 0.15, 0.30, 0.50]),
        "ptm_count": [float(x) for x in _parse_int_grid(str(getattr(args, "env_perturb_ptm_count_grid", "")), [0, 1, 2, 3])],
        "force_scale": _parse_float_grid(str(getattr(args, "env_perturb_force_scale_grid", "")), [0.9, 1.0, 1.1]),
        "cooling_rate": _parse_float_grid(str(getattr(args, "env_perturb_cooling_rate_grid", "")), [-1.0, 0.0, 1.0]),
        "hydro_strength": _parse_float_grid(str(getattr(args, "env_perturb_hydro_strength_grid", "")), [0.9, 1.0, 1.1]),
        "k_angle": _parse_float_grid(str(getattr(args, "env_perturb_k_angle_grid", "")), [20.0, 25.0, 30.0]),
        "theta0": _parse_float_grid(str(getattr(args, "env_perturb_theta0_grid", "")), [100.0, 109.5, 120.0]),
        "k_dihedral": _parse_float_grid(str(getattr(args, "env_perturb_k_dihedral_grid", "")), [0.5, 1.0, 2.0]),
        "phi0_alpha": _parse_float_grid(str(getattr(args, "env_perturb_phi0_alpha_grid", "")), [-70.0, -57.0, -45.0]),
        "ai_correction_active": _parse_float_grid(str(getattr(args, "env_perturb_ai_correction_active_grid", "")), [1.0]),
    }


def _pick_env_perturb_profile(
    *,
    args: argparse.Namespace,
    cycle_idx: int,
    protein_id: str,
    runtime_target: str,
    grids: Dict[str, List[float]],
) -> Dict[str, float]:
    base = {
        "temp": 300.0,
        "salt_conc": 0.1,
        "pH": 7.0,
        "ionic_strength": 0.15,
        "ptm_count": 0.0,
        "force_scale": 1.0,
        "cooling_rate": 0.0,
        "hydro_strength": 1.0,
        "k_angle": 25.0,
        "theta0": 109.5,
        "k_dihedral": 1.0,
        "phi0_alpha": -57.0,
        "ai_correction_active": 1.0,
    }
    if not bool(getattr(args, "env_perturb_enabled", True)):
        return base

    seed_material = f"{int(getattr(args, 'seed', 0))}:{int(cycle_idx)}:{protein_id}:{runtime_target}"
    seed_hash = hashlib.sha256(seed_material.encode("utf-8", errors="ignore")).hexdigest()
    rng = random.Random(int(seed_hash[:16], 16))
    out = dict(base)
    for key, values in grids.items():
        if not values:
            continue
        out[key] = float(values[rng.randrange(0, len(values))])
    out["ptm_count"] = float(int(round(out.get("ptm_count", 0.0))))
    out["ai_correction_active"] = float(1.0 if out.get("ai_correction_active", 1.0) >= 0.5 else 0.0)
    return out


def _apply_runtime_acceleration_profile(args: argparse.Namespace) -> Dict[str, Any]:
    env_updates = {
        "AI_ROUTER_RUNTIME_MODE": str(getattr(args, "ai_router_runtime_mode", "auto")).strip().lower(),
        "AI_ROUTER_AUTO_TRY_ONNX": "1" if bool(getattr(args, "ai_router_auto_try_onnx", True)) else "0",
        "AI_ROUTER_COMPILE_MODE": str(getattr(args, "ai_router_compile_mode", "reduce-overhead")).strip(),
        "AI_ROUTER_ONNX_PROVIDERS": str(
            getattr(args, "ai_router_onnx_providers", "ROCMExecutionProvider,CUDAExecutionProvider")
        ).strip(),
        "AI_ROUTER_DISABLE_EXPLORATION": "1",
        "AI_ROUTER_CACHE_INPUTS": "0",
        "AI_ROUTER_ONNX_IOBINDING_REQUIRED": "1"
        if bool(getattr(args, "onnx_require_iobinding", True))
        else "0",
        "AI_ROUTER_ONNX_ALLOW_CPU_COPY": "1"
        if bool(getattr(args, "onnx_allow_cpu_copy", False))
        else "0",
        "AI_ROUTER_ONNX_ALLOW_CPU": "0" if bool(getattr(args, "require_gpu", True)) else "1",
    }
    applied_env: Dict[str, str] = {}
    for key, value in env_updates.items():
        v = str(value).strip()
        if not v:
            continue
        os.environ[key] = v
        applied_env[key] = v

    # Stabilize torch.compile on long-running GPU loops (avoid CUDAGraph overwrite faults).
    if bool(getattr(args, "trainer_torch_compile", True)):
        os.environ.setdefault("TORCHINDUCTOR_USE_CUDAGRAPHS", "0")
        applied_env["TORCHINDUCTOR_USE_CUDAGRAPHS"] = str(os.environ.get("TORCHINDUCTOR_USE_CUDAGRAPHS", "0"))
        os.environ.setdefault("TORCHDYNAMO_SUPPRESS_ERRORS", "1")
        applied_env["TORCHDYNAMO_SUPPRESS_ERRORS"] = str(os.environ.get("TORCHDYNAMO_SUPPRESS_ERRORS", "1"))
        os.environ.setdefault("TORCHDYNAMO_CAPTURE_SCALAR_OUTPUTS", "1")
        applied_env["TORCHDYNAMO_CAPTURE_SCALAR_OUTPUTS"] = str(
            os.environ.get("TORCHDYNAMO_CAPTURE_SCALAR_OUTPUTS", "1")
        )

    tc = core_config.config.setdefault("torch_compile", {})
    tc["enabled"] = bool(getattr(args, "trainer_torch_compile", True))
    tc["mode"] = str(getattr(args, "trainer_torch_compile_mode", "reduce-overhead")).strip() or "reduce-overhead"
    tc["fullgraph"] = bool(getattr(args, "trainer_torch_compile_fullgraph", False))
    tc["dynamic"] = bool(getattr(args, "trainer_torch_compile_dynamic", True))

    return {
        "env": applied_env,
        "torch_compile": dict(tc),
    }


def _run_rust_native_probe(
    *,
    args: argparse.Namespace,
    cycle_prefix: str,
    cycle_idx: int,
) -> Dict[str, Any]:
    enabled = bool(getattr(args, "rust_native_probe_enabled", False))
    every = max(1, int(getattr(args, "rust_native_probe_every_cycles", 1)))
    if not enabled:
        return {"enabled": False, "attempted": False, "reason": "disabled"}
    if int(cycle_idx) % int(every) != 0:
        return {
            "enabled": True,
            "attempted": False,
            "reason": "cycle_skip",
            "cycle": int(cycle_idx),
            "every_cycles": int(every),
        }

    out_json = f"{cycle_prefix}_rust_native_probe.json"
    raw_json = f"{cycle_prefix}_rust_native_probe_raw.json"
    cmd = [
        str(sys.executable),
        "tools/run_rust_native_inference_poc.py",
        "--target",
        str(getattr(args, "rust_native_probe_target", "Chignolin")),
        "--batch",
        str(int(getattr(args, "rust_native_probe_batch", 1))),
        "--atoms",
        str(int(getattr(args, "rust_native_probe_atoms", 0))),
        "--topo-dim",
        str(int(getattr(args, "rust_native_probe_topo_dim", 64))),
        "--sim-dim",
        str(int(getattr(args, "rust_native_probe_sim_dim", 19))),
        "--seed",
        str(int(getattr(args, "seed", 0)) + int(cycle_idx)),
        "--cargo-manifest",
        str(getattr(args, "rust_native_probe_cargo_manifest", "rust_engine/Cargo.toml")),
        "--rust-out-json",
        str(raw_json),
        "--out-json",
        str(out_json),
    ]
    ckpt = str(getattr(args, "rust_native_probe_ai_router_checkpoint", "")).strip()
    if ckpt:
        cmd.extend(["--ai-router-checkpoint", ckpt])
        if bool(getattr(args, "rust_native_probe_ai_router_checkpoint_strict", False)):
            cmd.append("--ai-router-checkpoint-strict")
        else:
            cmd.append("--no-ai-router-checkpoint-strict")
    onnx_path = str(getattr(args, "rust_native_probe_onnx_path", "")).strip()
    if onnx_path:
        cmd.extend(["--onnx-path", onnx_path])

    timeout_sec = max(1.0, float(getattr(args, "rust_native_probe_timeout_sec", 1800.0)))
    try:
        run = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=float(timeout_sec),
        )
        summary_payload = _load_json(out_json, {})
        ok = bool(run.returncode == 0 and isinstance(summary_payload, dict) and summary_payload.get("ok", False))
        return {
            "enabled": True,
            "attempted": True,
            "ok": bool(ok),
            "returncode": int(run.returncode),
            "command": cmd,
            "out_json": os.path.abspath(out_json),
            "raw_json": os.path.abspath(raw_json),
            "summary": summary_payload if isinstance(summary_payload, dict) else {},
            "stdout_tail": str(run.stdout or "")[-1000:],
            "stderr_tail": str(run.stderr or "")[-1000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "enabled": True,
            "attempted": True,
            "ok": False,
            "error": f"timeout:{float(timeout_sec):.1f}s",
            "command": cmd,
            "stdout_tail": str(exc.stdout or "")[-1000:],
            "stderr_tail": str(exc.stderr or "")[-1000:],
        }
    except Exception as exc:
        return {
            "enabled": True,
            "attempted": True,
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "command": cmd,
        }


def _load_json(path: str, default: Any) -> Any:
    if (not str(path).strip()) or (not os.path.exists(path)):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save_json(path: str, payload: Any) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def _pid_alive(pid: int) -> bool:
    try:
        if int(pid) <= 0:
            return False
        os.kill(int(pid), 0)
        return True
    except Exception:
        return False


def _pid_parent(pid: int) -> int:
    try:
        with open(f"/proc/{int(pid)}/stat", "r", encoding="utf-8", errors="ignore") as f:
            parts = f.read().strip().split()
        # Linux /proc/<pid>/stat format: field 4 is ppid.
        return int(parts[3]) if len(parts) > 3 else -1
    except Exception:
        return -1


def _update_runtime_state(
    *,
    args: argparse.Namespace,
    state: Dict[str, Any],
    cycle_idx: int,
    date_tag: str,
    phase: str,
    current_target: str = "",
    note: str = "",
    persist: bool = True,
) -> None:
    state["phase"] = str(phase)
    state["current_cycle"] = int(cycle_idx)
    state["current_date_tag"] = str(date_tag)
    state["current_target"] = str(current_target or "")
    state["current_note"] = str(note or "")
    state["updated_at_local"] = _now_local()
    if bool(persist):
        _save_state(str(args.state_json), state)


def _datagen_worker(payload: Dict[str, Any]) -> None:
    log_path = str(payload.get("log_path", ""))
    out_json = str(payload.get("out_json", ""))
    result: Dict[str, Any] = {"ok": False, "error": "unknown"}
    try:
        device_i = str(payload.get("device", "cuda")).strip().lower()
        device_id_i = int(payload.get("device_id", 0))
        require_gpu = bool(payload.get("require_gpu", True))
        core_config.config.setdefault("device", {})
        core_config.config["device"]["type"] = str(device_i)
        if device_i == "cuda":
            core_config.config["device"]["id"] = int(device_id_i)
        if require_gpu:
            if device_i != "cuda":
                raise RuntimeError(f"gpu_required_but_device_is_{device_i}")
            if not torch.cuda.is_available():
                raise RuntimeError("gpu_required_but_cuda_unavailable")
            dev_count = int(torch.cuda.device_count())
            if dev_count <= 0:
                raise RuntimeError("gpu_required_but_no_cuda_device")
            if (device_id_i < 0) or (device_id_i >= dev_count):
                raise RuntimeError(f"gpu_device_id_out_of_range:{device_id_i}/{dev_count}")
            os.environ["FORCE_RUST_HIP"] = "1"
            os.environ["RUST_HIP_USE_GPU_NBLIST_BUILDER"] = "1"
            os.environ["RUST_HIP_NBLIST_AUTOGROW"] = "1"
            os.environ["AI_ROUTER_ONNX_ALLOW_CPU"] = "0"
            os.environ["MD_GPU_ONLY"] = "1"
        target = str(payload.get("target", ""))
        ca_residues = int(payload.get("ca_residues", 0))
        if target and ca_residues > 0:
            _register_dynamic_target(target, ca_residues)
        os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as io_log:
            with redirect_stdout(io_log), redirect_stderr(io_log):
                gen = DataGenerator(
                    target=target,
                    total_samples=int(payload.get("total_samples", 0)),
                    noise=float(payload.get("noise", 0.1)),
                    output_dir=str(payload.get("output_dir", "")),
                    train_ratio=float(payload.get("train_ratio", 0.8)),
                    val_ratio=float(payload.get("val_ratio", 0.1)),
                    fast_mode=False,
                    explicit_2bead=True,
                    residual_mode=bool(payload.get("residual_mode", True)),
                    reference_cutoff=float(payload.get("reference_cutoff", 14.0)),
                    reference_max_neighbors=int(payload.get("reference_max_neighbors", 160)),
                    reference_force_cap=float(payload.get("reference_force_cap", 100.0)),
                    force_backend=str(payload.get("force_backend", "auto")),
                    sim_param_overrides=(payload.get("sim_params", {}) if isinstance(payload.get("sim_params", {}), dict) else {}),
                )
                ok = bool(gen.generate())
        result = {"ok": bool(ok), "error": "" if ok else "data_generation_failed"}
    except Exception as exc:
        result = {"ok": False, "error": str(exc)}
    _save_json(out_json, result)


def _run_datagen_with_timeout(
    *,
    target: str,
    total_samples: int,
    noise: float,
    output_dir: str,
    train_ratio: float,
    val_ratio: float,
    residual_mode: bool,
    reference_cutoff: float,
    reference_max_neighbors: int,
    reference_force_cap: float,
    force_backend: str,
    sim_params: Optional[Dict[str, float]],
    device: str,
    device_id: int,
    require_gpu: bool,
    ca_residues: int,
    log_path: str,
    timeout_sec: float,
) -> Tuple[bool, str]:
    fd, out_json = tempfile.mkstemp(prefix=".datagen_", suffix=".json", dir=os.path.dirname(log_path) or ".")
    os.close(fd)
    worker_payload = {
        "target": str(target),
        "total_samples": int(total_samples),
        "noise": float(noise),
        "output_dir": str(output_dir),
        "train_ratio": float(train_ratio),
        "val_ratio": float(val_ratio),
        "residual_mode": bool(residual_mode),
        "reference_cutoff": float(reference_cutoff),
        "reference_max_neighbors": int(reference_max_neighbors),
        "reference_force_cap": float(reference_force_cap),
        "force_backend": str(force_backend),
        "sim_params": dict(sim_params or {}),
        "device": str(device),
        "device_id": int(device_id),
        "require_gpu": bool(require_gpu),
        "ca_residues": int(ca_residues),
        "log_path": str(log_path),
        "out_json": str(out_json),
    }
    try:
        timeout_i = max(float(timeout_sec), 0.0)
        if timeout_i <= 0.0:
            _datagen_worker(worker_payload)
            out = _load_json(out_json, {}) if os.path.exists(out_json) else {}
            return bool(out.get("ok", False)), str(out.get("error", ""))

        ctx = mp.get_context("spawn")
        proc = ctx.Process(target=_datagen_worker, args=(worker_payload,))
        proc.start()
        proc.join(timeout_i)
        if proc.is_alive():
            try:
                proc.terminate()
            except Exception:
                pass
            proc.join(timeout=5.0)
            return False, f"datagen_timeout:{timeout_i:.1f}s"
        out = _load_json(out_json, {}) if os.path.exists(out_json) else {}
        if isinstance(out, dict):
            return bool(out.get("ok", False)), str(out.get("error", ""))
        return False, "datagen_no_result"
    finally:
        if os.path.exists(out_json):
            try:
                os.unlink(out_json)
            except Exception:
                pass


def _meta_learning_worker(payload: Dict[str, Any]) -> None:
    log_path = str(payload.get("log_path", ""))
    out_json = str(payload.get("out_json", ""))
    env_set = payload.get("env", {}) if isinstance(payload.get("env"), dict) else {}
    env_backup: Dict[str, Optional[str]] = {}
    result: Dict[str, Any] = {
        "ok": False,
        "error": "meta_worker_failed",
        "generated_at_local": _now_local(),
        "best_checkpoint": "",
        "training_payload": {},
    }
    try:
        for k, v in env_set.items():
            env_backup[k] = os.environ.get(k)
            os.environ[k] = str(v)

        os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as io_log:
            with redirect_stdout(io_log), redirect_stderr(io_log):
                tp = run_training_pipeline(
                    target=str(payload.get("training_target", "*")),
                    use_hp_search=bool(payload.get("training_hp_search", False)),
                    schedule=str(payload.get("training_schedule", "size_ascending")),
                    seed=int(payload.get("seed", 0)),
                    max_targets=None if int(payload.get("training_max_targets", 0)) <= 0 else int(payload.get("training_max_targets", 0)),
                    data_source="distilled",
                    distilled_manifest=str(payload.get("distilled_manifest", "")),
                    distilled_split_col="split",
                    distilled_min_quality=None,
                    distilled_max_samples_per_shard=None,
                    distilled_sample_weight_col="sampling_weight",
                    distilled_default_shard_weight=1.0,
                    distilled_quality_weight_alpha=0.0,
                    distilled_min_sampling_weight=1e-6,
                    distilled_use_weighted_sampler=True,
                    distilled_weighted_sampler_replacement=True,
                    initial_checkpoint=str(payload.get("initial_checkpoint", "")),
                    checkpoint_strict=False,
                    carry_over_checkpoint=False,
                    checkpoint_dir=str(payload.get("checkpoint_dir", "models/curriculum_live_unseen")),
                    early_stop_patience=int(payload.get("training_early_stop_patience", 6)),
                    curriculum_summary_json=str(payload.get("summary_json", "")),
                    curriculum_summary_csv=str(payload.get("summary_csv", "")),
                    run_tag=str(payload.get("run_tag", "")),
                )
        result = {
            "ok": True,
            "error": "",
            "generated_at_local": _now_local(),
            "best_checkpoint": _extract_best_checkpoint(tp),
            "training_payload": tp,
        }
    except Exception as exc:
        result = {
            "ok": False,
            "error": str(exc),
            "generated_at_local": _now_local(),
            "best_checkpoint": "",
            "training_payload": {},
        }
    finally:
        for k, old in env_backup.items():
            if old is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = old
    _save_json(out_json, result)


def _acquire_instance_lock(lock_path: str) -> Tuple[int, Dict[str, Any]]:
    path = str(lock_path).strip()
    if not path:
        raise RuntimeError("empty_lock_path")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o664)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        owner = ""
        try:
            os.lseek(fd, 0, os.SEEK_SET)
            owner = os.read(fd, 256).decode("utf-8", errors="ignore").strip()
        except Exception:
            owner = ""
        os.close(fd)
        return -1, {"ok": False, "lock_path": os.path.abspath(path), "owner": owner}
    os.ftruncate(fd, 0)
    os.write(fd, f"{os.getpid()}\n".encode("utf-8"))
    os.fsync(fd)
    return fd, {"ok": True, "lock_path": os.path.abspath(path), "owner": str(os.getpid())}


def _build_uniprot_search_url(query: str, size: int, *, cursor: str = "") -> str:
    params = {
        "query": str(query).strip(),
        "fields": "accession,protein_name",
        "format": "tsv",
        # UniProt REST rejects large `size` values (HTTP 400). Keep requests within supported bounds.
        "size": str(min(UNIPROT_QUERY_MAX_SIZE, max(1, int(size)))),
    }
    cur = str(cursor).strip()
    if cur:
        params["cursor"] = cur
    return "https://rest.uniprot.org/uniprotkb/search?" + urllib.parse.urlencode(params)


def _fetch_uniprot_candidate_rows(query: str, size: int, timeout_sec: float) -> List[Dict[str, str]]:
    page = _fetch_uniprot_candidate_page(query=query, size=size, timeout_sec=timeout_sec, cursor="")
    rows = page.get("rows", [])
    return rows if isinstance(rows, list) else []


def _extract_uniprot_next_cursor(link_header: str) -> str:
    s = str(link_header or "").strip()
    if not s:
        return ""
    # Example: <https://...&cursor=abc&size=5>; rel="next"
    m = re.search(r"<([^>]+)>;\s*rel=\"next\"", s)
    if not m:
        return ""
    url = str(m.group(1)).strip()
    if not url:
        return ""
    try:
        q = urllib.parse.urlparse(url).query
        params = urllib.parse.parse_qs(q)
        cur = params.get("cursor", [""])[0]
        return str(cur).strip()
    except Exception:
        return ""


def _fetch_uniprot_candidate_page(
    query: str,
    size: int,
    timeout_sec: float,
    cursor: str = "",
) -> Dict[str, Any]:
    url = _build_uniprot_search_url(query=query, size=size, cursor=cursor)
    req = urllib.request.Request(
        url=str(url).strip(),
        headers={"User-Agent": "md-live-learning-bot/1.0"},
    )
    with urllib.request.urlopen(req, timeout=float(timeout_sec)) as resp:
        payload = resp.read()
        link_header = str(resp.headers.get("Link", "") or "")
        total_results = int(_safe_float(resp.headers.get("X-Total-Results", 0), 0))
    raw = payload.decode("utf-8", errors="ignore")
    lines = [ln for ln in raw.splitlines() if ln.strip()]
    out: List[Dict[str, str]] = []
    if len(lines) > 1:
        for ln in lines[1:]:
            parts = ln.split("\t")
            if len(parts) < 1:
                continue
            acc = str(parts[0]).strip().upper()
            if not acc:
                continue
            pname = str(parts[1]).strip() if len(parts) > 1 else ""
            out.append({"uniprot_id": acc, "protein_name": pname})
    return {
        "rows": out,
        "next_cursor": _extract_uniprot_next_cursor(link_header),
        "cursor_in": str(cursor).strip(),
        "total_results": int(total_results),
    }


def _fetch_afdb_global_metric(uniprot_id: str, timeout_sec: float) -> Dict[str, Any]:
    acc = str(uniprot_id).strip().upper()
    if not acc:
        return {"ok": False, "error": "empty_uniprot_id"}
    url = f"https://alphafold.ebi.ac.uk/api/prediction/{urllib.parse.quote(acc)}"
    try:
        payload = _download_json(url=url, timeout_sec=timeout_sec)
        if not isinstance(payload, list) or len(payload) == 0:
            return {"ok": False, "error": "empty_payload", "uniprot_id": acc}
        row = payload[0] if isinstance(payload[0], dict) else {}
        score = _safe_float(row.get("globalMetricValue", 0.0), 0.0)
        return {
            "ok": True,
            "uniprot_id": acc,
            "global_metric": float(score),
            "entry_id": str(row.get("entryId", "")),
            "pdb_url": str(row.get("pdbUrl", "")),
            "is_reviewed": bool(row.get("isReviewed", False)),
        }
    except urllib.error.HTTPError as exc:
        return {"ok": False, "uniprot_id": acc, "error": f"http_{int(exc.code)}"}
    except Exception as exc:
        return {"ok": False, "uniprot_id": acc, "error": str(exc)}


def _clean_protein_name(value: str) -> str:
    s = str(value).strip()
    if not s:
        return ""
    s = re.sub(r"\s*\([^)]*\)", "", s).strip()
    return s


def _auto_sync_afdb_sources(
    sources_csv: str,
    state: Dict[str, Any],
    cache_json: str,
    query: str,
    query_size: int,
    min_global_metric: float,
    add_per_cycle: int,
    timeout_sec: float,
    max_metric_lookups_per_cycle: int,
    start_cursor: str = "",
    pages_per_cycle: int = 1,
    reset_cursor_on_empty: bool = True,
) -> Dict[str, Any]:
    if int(add_per_cycle) <= 0:
        return {"enabled": False, "added_rows": 0}

    current_df = _read_csv_if_exists(sources_csv)
    current_df = _normalize_source_columns(current_df) if (not current_df.empty) else _normalize_source_columns(pd.DataFrame())
    known_ids = set()
    if not current_df.empty:
        for rec in current_df.to_dict(orient="records"):
            known_ids.add(_compose_protein_id_from_row(rec))
    known_ids.update(str(x) for x in state.get("trained_protein_ids", []))
    known_ids.update(str(x) for x in state.get("failed_protein_ids", []))

    cache_raw = _load_json(cache_json, default={})
    score_cache = cache_raw if isinstance(cache_raw, dict) else {}
    pages_used: List[Dict[str, Any]] = []
    fetched: List[Dict[str, str]] = []
    cursor_now = str(start_cursor or "").strip()
    max_pages = int(max(1, pages_per_cycle))
    for _ in range(max_pages):
        page = _fetch_uniprot_candidate_page(
            query=query,
            size=query_size,
            timeout_sec=timeout_sec,
            cursor=cursor_now,
        )
        page_rows = page.get("rows", [])
        if not isinstance(page_rows, list):
            page_rows = []
        fetched.extend(page_rows)
        pages_used.append(
            {
                "cursor_in": str(page.get("cursor_in", "")),
                "rows": int(len(page_rows)),
                "total_results": int(_safe_float(page.get("total_results", 0), 0)),
            }
        )
        next_cursor = str(page.get("next_cursor", "")).strip()
        if (not next_cursor) or (len(page_rows) <= 0):
            cursor_now = next_cursor
            break
        cursor_now = next_cursor

    if bool(reset_cursor_on_empty) and (len(fetched) <= 0) and str(start_cursor).strip():
        fallback_page = _fetch_uniprot_candidate_page(
            query=query,
            size=query_size,
            timeout_sec=timeout_sec,
            cursor="",
        )
        fallback_rows = fallback_page.get("rows", [])
        if isinstance(fallback_rows, list):
            fetched = fallback_rows
            pages_used.append(
                {
                    "cursor_in": "",
                    "rows": int(len(fallback_rows)),
                    "total_results": int(_safe_float(fallback_page.get("total_results", 0), 0)),
                    "fallback_reset": True,
                }
            )
            cursor_now = str(fallback_page.get("next_cursor", "")).strip()

    added_rows: List[Dict[str, Any]] = []
    scanned = 0
    cache_updates = 0
    metric_lookups = 0
    lookup_budget = max(1, int(max_metric_lookups_per_cycle))
    budget_exhausted = False
    for row in fetched:
        if len(added_rows) >= int(add_per_cycle):
            break
        scanned += 1
        acc = str(row.get("uniprot_id", "")).strip().upper()
        if not acc:
            continue
        pid = f"U:{acc}"
        if pid in known_ids:
            continue

        cached = score_cache.get(acc, {}) if isinstance(score_cache.get(acc, {}), dict) else {}
        has_cached_score = "global_metric" in cached
        if has_cached_score:
            metric_info = {"ok": True, "uniprot_id": acc, "global_metric": _safe_float(cached.get("global_metric", 0.0), 0.0)}
        else:
            if metric_lookups >= lookup_budget:
                budget_exhausted = True
                break
            metric_lookups += 1
            metric_info = _fetch_afdb_global_metric(uniprot_id=acc, timeout_sec=timeout_sec)
            if metric_info.get("ok"):
                score_cache[acc] = {
                    "global_metric": float(metric_info.get("global_metric", 0.0)),
                    "entry_id": str(metric_info.get("entry_id", "")),
                    "updated_at_local": _now_local(),
                }
                cache_updates += 1

        score = _safe_float(metric_info.get("global_metric", 0.0), 0.0)
        if (not bool(metric_info.get("ok", False))) or (score < float(min_global_metric)):
            continue

        pname = _clean_protein_name(str(row.get("protein_name", "")))
        if pname:
            base_name = pname[:56]
            target = f"Auto_{_slug(base_name)}_{acc}"
        else:
            target = f"Auto_{acc}"
        out_row = {
            "target": target,
            "pdb_id": "",
            "uniprot_id": acc,
            "priority": float(score),
            "pdb_url": "",
            "afdb_url": "",
            "notes": f"auto_afdb_online global_metric={score:.2f}",
        }
        added_rows.append(out_row)
        known_ids.add(pid)

    if len(added_rows) > 0:
        merged = pd.concat([current_df, pd.DataFrame(added_rows)], ignore_index=True)
        merged = _normalize_source_columns(merged)
        merged = merged.drop_duplicates(subset=["target", "pdb_id", "uniprot_id"], keep="last")
        merged = merged.sort_values(by=["priority", "target"], ascending=[False, True]).reset_index(drop=True)
        os.makedirs(os.path.dirname(sources_csv) or ".", exist_ok=True)
        merged.to_csv(sources_csv, index=False)

    if cache_updates > 0:
        _save_json(cache_json, score_cache)

    return {
        "enabled": True,
        "query": str(query),
        "query_size": int(query_size),
        "query_cursor_in": str(start_cursor or ""),
        "query_cursor_out": str(cursor_now or ""),
        "pages_per_cycle": int(max_pages),
        "pages_used": pages_used,
        "fetched_rows_total": int(len(fetched)),
        "min_global_metric": float(min_global_metric),
        "scanned_candidates": int(scanned),
        "added_rows": int(len(added_rows)),
        "added_uniprot_ids": [str(r.get("uniprot_id", "")) for r in added_rows],
        "sources_csv": os.path.abspath(sources_csv),
        "score_cache_json": os.path.abspath(cache_json),
        "cache_updates": int(cache_updates),
        "metric_lookups": int(metric_lookups),
        "metric_lookup_budget": int(lookup_budget),
        "metric_lookup_budget_exhausted": bool(budget_exhausted),
    }


def _sync_md_sources_from_catalog_urls(
    md_sources_csv: str,
    catalog_urls: Sequence[str],
    timeout_sec: float,
) -> Dict[str, Any]:
    urls = [str(x).strip() for x in catalog_urls if str(x).strip()]
    if len(urls) == 0:
        return {"enabled": False, "added_rows": 0}

    base_df = _read_csv_if_exists(md_sources_csv)
    base_df = _normalize_md_source_columns(base_df) if (not base_df.empty) else _normalize_md_source_columns(pd.DataFrame())

    imported_frames: List[pd.DataFrame] = [base_df]
    per_url: List[Dict[str, Any]] = []
    for url in urls:
        status: Dict[str, Any] = {"url": url, "ok": False, "rows": 0}
        tmp_path = ""
        try:
            if url.lower().startswith("http://") or url.lower().startswith("https://"):
                fd, tmp_path = tempfile.mkstemp(prefix=".md_catalog_", suffix=".csv")
                os.close(fd)
                dl = _refresh_csv_from_url(url=url, out_csv=tmp_path, timeout_sec=timeout_sec)
                if not dl.get("refreshed", False):
                    raise RuntimeError("catalog_refresh_failed")
                src_path = tmp_path
            else:
                src_path = url
            df = pd.read_csv(src_path)
            # Allow import from broader manifest schemas, e.g.:
            # target,path,engine,label,...
            if ("md_path" not in df.columns) and ("path" in df.columns):
                df["md_path"] = df["path"]
            if ("md_url" not in df.columns) and ("url" in df.columns):
                df["md_url"] = df["url"]
            if ("label" not in df.columns) and ("engine" in df.columns):
                df["label"] = df["engine"].map(lambda x: f"auto_{_clean_str(x)}")
            df = _normalize_md_source_columns(df)
            imported_frames.append(df)
            status.update({"ok": True, "rows": int(df.shape[0])})
        except Exception as exc:
            status.update({"ok": False, "error": str(exc)})
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
        per_url.append(status)

    merged = pd.concat(imported_frames, ignore_index=True) if len(imported_frames) > 0 else _normalize_md_source_columns(pd.DataFrame())
    if not merged.empty:
        merged["_pid"] = merged.to_dict(orient="records")
        merged["_pid"] = merged["_pid"].map(lambda x: _compose_protein_id_from_row(x if isinstance(x, dict) else {}))
        merged = merged.drop_duplicates(subset=["_pid"], keep="last")
        merged = merged.drop(columns=["_pid"], errors="ignore")
        merged = merged.reset_index(drop=True)
    os.makedirs(os.path.dirname(md_sources_csv) or ".", exist_ok=True)
    merged.to_csv(md_sources_csv, index=False)
    rows_before = int(base_df.shape[0]) if isinstance(base_df, pd.DataFrame) else 0
    rows_after = int(merged.shape[0])
    return {
        "enabled": True,
        "catalog_urls": urls,
        "rows_before": rows_before,
        "rows_after": rows_after,
        "added_rows": int(max(0, rows_after - rows_before)),
        "per_url": per_url,
        "md_sources_csv": os.path.abspath(md_sources_csv),
    }


def _download_file(url: str, out_path: str, timeout_sec: float) -> Dict[str, Any]:
    if not str(url).strip():
        return {"ok": False, "path": out_path, "error": "empty_url"}
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".dl_", suffix=".bin", dir=os.path.dirname(out_path) or ".")
    os.close(fd)
    try:
        with urllib.request.urlopen(str(url).strip(), timeout=float(timeout_sec)) as resp:
            payload = resp.read()
        with open(tmp, "wb") as f:
            f.write(payload)
        os.replace(tmp, out_path)
        return {"ok": True, "path": os.path.abspath(out_path), "bytes": int(len(payload))}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "path": out_path, "error": f"http_{int(exc.code)}"}
    except Exception as exc:  # pragma: no cover
        return {"ok": False, "path": out_path, "error": str(exc)}
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _read_csv_if_exists(path: str) -> pd.DataFrame:
    if not str(path).strip() or (not os.path.exists(path)):
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _ensure_sources_csv(path: str) -> Dict[str, Any]:
    out_path = str(path).strip()
    if not out_path:
        return {"enabled": False, "ok": False, "reason": "empty_path"}
    existed = os.path.exists(out_path)
    raw = _read_csv_if_exists(out_path)
    rows_before = int(raw.shape[0]) if not raw.empty else 0
    normalized = _normalize_source_columns(raw) if not raw.empty else _normalize_source_columns(pd.DataFrame())
    rows_after = int(normalized.shape[0]) if not normalized.empty else 0
    needs_write = (not existed) or (list(normalized.columns) != list(raw.columns))
    if needs_write:
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        normalized.to_csv(out_path, index=False)
    return {
        "enabled": True,
        "ok": True,
        "created": bool((not existed) and needs_write),
        "normalized": bool(needs_write),
        "rows_before": int(rows_before),
        "rows_after": int(rows_after),
        "path": os.path.abspath(out_path),
    }


def _ensure_md_sources_csv(path: str) -> Dict[str, Any]:
    out_path = str(path).strip()
    if not out_path:
        return {"enabled": False, "ok": False, "reason": "empty_path"}
    existed = os.path.exists(out_path)
    raw = _read_csv_if_exists(out_path)
    rows_before = int(raw.shape[0]) if not raw.empty else 0
    normalized = _normalize_md_source_columns(raw) if not raw.empty else _normalize_md_source_columns(pd.DataFrame())
    rows_after = int(normalized.shape[0]) if not normalized.empty else 0
    needs_write = (not existed) or (list(normalized.columns) != list(raw.columns))
    if needs_write:
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        normalized.to_csv(out_path, index=False)
    return {
        "enabled": True,
        "ok": True,
        "created": bool((not existed) and needs_write),
        "normalized": bool(needs_write),
        "rows_before": int(rows_before),
        "rows_after": int(rows_after),
        "path": os.path.abspath(out_path),
    }


def _extract_training_throughput_stats(log_path: str) -> Dict[str, Any]:
    path = str(log_path).strip()
    out: Dict[str, Any] = {
        "log_path": path,
        "count": 0,
        "last": None,
        "avg": None,
        "min": None,
        "max": None,
    }
    if (not path) or (not os.path.exists(path)):
        return out
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            blob = f.read()
    except Exception:
        return out
    vals: List[float] = []
    for m in re.finditer(r"Train Throughput:\s*([0-9]+(?:\.[0-9]+)?)", blob):
        try:
            vals.append(float(m.group(1)))
        except Exception:
            continue
    if len(vals) <= 0:
        return out
    out["count"] = int(len(vals))
    out["last"] = float(vals[-1])
    out["avg"] = float(sum(vals) / float(len(vals)))
    out["min"] = float(min(vals))
    out["max"] = float(max(vals))
    return out


def _load_state(path: str) -> Dict[str, Any]:
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            if isinstance(payload, dict):
                return payload
        except Exception:
            pass
    return {
        "version": 1,
        "created_at_local": _now_local(),
        "updated_at_local": _now_local(),
        "cycles_completed": 0,
        "trained_protein_ids": [],
        "failed_protein_ids": [],
        "fail_counts": {},
        "latest_checkpoint": "",
        "proteins": {},
    }


def _save_state(path: str, state: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    state["updated_at_local"] = _now_local()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def _append_jsonl(path: str, row: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _read_recent_jsonl(path: str, window: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if (not str(path).strip()) or (not os.path.exists(path)):
        return out
    max_rows = int(max(1, window))
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            s = str(line).strip()
            if not s:
                continue
            try:
                row = json.loads(s)
            except Exception:
                continue
            if isinstance(row, dict):
                out.append(row)
    if len(out) <= max_rows:
        return out
    return out[-max_rows:]


def _evaluate_success_gate(
    rows: Sequence[Dict[str, Any]],
    *,
    warmup_cycles: int,
    min_pass_rate_pct: float,
    min_core_pass_rate_pct: float,
    min_avg_trained_per_cycle: float,
    max_failed_sum: int,
    max_consecutive_fail: int,
) -> Dict[str, Any]:
    total = int(len(rows))
    if total <= 0:
        return {
            "pass": True,
            "reason": "no_rows",
            "window_rows": 0,
            "pass_rate_pct": 0.0,
            "core_pass_rate_pct": 0.0,
            "avg_trained_per_cycle": 0.0,
            "failed_sum": 0,
            "consecutive_fail_count": 0,
            "failed_checks": [],
        }

    pass_count = 0
    core_pass_count = 0
    trained_sum = 0
    failed_sum = 0
    consecutive_fail = 0
    for row in rows:
        if bool(row.get("pass", False)):
            pass_count += 1
        if bool(row.get("core_pass", row.get("pass", False))):
            core_pass_count += 1
        trained_sum += int(_safe_float(row.get("trained_ids_count", 0), 0))
        failed_sum += int(_safe_float(row.get("failed_ids_count", 0), 0))
    for row in reversed(rows):
        if bool(row.get("pass", False)):
            break
        consecutive_fail += 1

    pass_rate_pct = (100.0 * float(pass_count) / float(total)) if total > 0 else 0.0
    core_pass_rate_pct = (100.0 * float(core_pass_count) / float(total)) if total > 0 else 0.0
    avg_trained = (float(trained_sum) / float(total)) if total > 0 else 0.0

    # Warmup window: gather enough signal before strict gate.
    warmup_n = int(max(0, warmup_cycles))
    if total < max(1, warmup_n):
        return {
            "pass": True,
            "reason": "warmup",
            "window_rows": int(total),
            "pass_rate_pct": float(pass_rate_pct),
            "core_pass_rate_pct": float(core_pass_rate_pct),
            "avg_trained_per_cycle": float(avg_trained),
            "failed_sum": int(failed_sum),
            "consecutive_fail_count": int(consecutive_fail),
            "failed_checks": [],
        }

    failed_checks: List[str] = []
    if float(pass_rate_pct) < float(min_pass_rate_pct):
        failed_checks.append(
            f"pass_rate_pct:{pass_rate_pct:.2f}<min:{float(min_pass_rate_pct):.2f}"
        )
    if float(core_pass_rate_pct) < float(min_core_pass_rate_pct):
        failed_checks.append(
            f"core_pass_rate_pct:{core_pass_rate_pct:.2f}<min:{float(min_core_pass_rate_pct):.2f}"
        )
    if float(avg_trained) < float(min_avg_trained_per_cycle):
        failed_checks.append(
            f"avg_trained_per_cycle:{avg_trained:.3f}<min:{float(min_avg_trained_per_cycle):.3f}"
        )
    if int(max_failed_sum) >= 0 and int(failed_sum) > int(max_failed_sum):
        failed_checks.append(f"failed_sum:{int(failed_sum)}>max:{int(max_failed_sum)}")
    if int(max_consecutive_fail) >= 0 and int(consecutive_fail) > int(max_consecutive_fail):
        failed_checks.append(
            f"consecutive_fail_count:{int(consecutive_fail)}>max:{int(max_consecutive_fail)}"
        )

    return {
        "pass": bool(len(failed_checks) == 0),
        "reason": "ok" if len(failed_checks) == 0 else "threshold_miss",
        "window_rows": int(total),
        "pass_rate_pct": float(pass_rate_pct),
        "core_pass_rate_pct": float(core_pass_rate_pct),
        "avg_trained_per_cycle": float(avg_trained),
        "failed_sum": int(failed_sum),
        "consecutive_fail_count": int(consecutive_fail),
        "failed_checks": failed_checks,
    }


def _classify_failure_category(reason: str, event: str) -> str:
    r = str(reason or "").strip().lower()
    e = str(event or "").strip().lower()
    if ("deferred_large_cycle" in e) or ("deferred_large_cycle" in r) or ("wait_large_cycle" in r):
        return "oversize_wait_large_cycle"
    if "high_ca_count_hard_cap" in r:
        return "oversize_hard_cap"
    if "high_ca_count" in r or "skipped_oversize" in r:
        return "oversize"
    if "low_ca_count" in r:
        return "low_ca"
    if "no_structure_path" in r:
        return "missing_structure"
    if ("stale_failed_state" in r) or (r == "trained") or (r.startswith("trained;")):
        return "stale_state"
    if ("out of memory" in r) or ("cuda oom" in r) or ("cublas" in r):
        if ("training_failed" in e) or ("training" in r):
            return "training_oom"
        return "datagen_oom"
    if "timeout" in r:
        if ("training_failed" in e) or ("training" in r):
            return "training_timeout"
        return "datagen_timeout"
    if ("candidate_datagen_error" in e) or ("data_generation_failed" in r) or ("datagen" in r):
        return "datagen_failure"
    if ("training_transient_failure" in e) or ("too many open files" in r) or ("resource temporarily unavailable" in r):
        return "training_transient"
    if ("training_failed" in e) or ("training" in r):
        return "training_failure"
    if ("candidate_exception" in e) or ("exception" in r):
        return "exception"
    return "other"


def _extract_quality_row_from_summary(summary_json: str) -> Dict[str, Any]:
    payload = _load_json(str(summary_json), {})
    if not isinstance(payload, dict):
        return {"exists": False}
    tp = payload.get("training_payload", {}) if isinstance(payload.get("training_payload"), dict) else {}
    result = tp.get("result", {}) if isinstance(tp.get("result"), dict) else {}
    best_val_loss = _safe_float(result.get("best_val_loss", float("nan")), float("nan"))
    test_rmse = _safe_float(result.get("test_rmse", float("nan")), float("nan"))
    test_mae = _safe_float(result.get("test_mae", float("nan")), float("nan"))
    epochs = _safe_float(result.get("epochs_trained", float("nan")), float("nan"))
    has_metric = not (pd.isna(best_val_loss) and pd.isna(test_rmse) and pd.isna(test_mae))
    return {
        "exists": bool(has_metric),
        "best_val_loss": (None if pd.isna(best_val_loss) else float(best_val_loss)),
        "test_rmse": (None if pd.isna(test_rmse) else float(test_rmse)),
        "test_mae": (None if pd.isna(test_mae) else float(test_mae)),
        "epochs_trained": (None if pd.isna(epochs) else float(epochs)),
    }


def _mean_opt(values: Sequence[Optional[float]]) -> Optional[float]:
    rows = [float(x) for x in values if x is not None]
    if len(rows) <= 0:
        return None
    return float(sum(rows) / float(len(rows)))


def _pct_delta_opt(new_v: Optional[float], old_v: Optional[float]) -> Optional[float]:
    if new_v is None or old_v is None:
        return None
    denom = max(abs(float(old_v)), 1e-9)
    return float((float(new_v) - float(old_v)) / denom * 100.0)


def _evaluate_quality_guard(
    rows: Sequence[Dict[str, Any]],
    *,
    window: int,
    warmup_cycles: int,
    min_metrics_rows: int,
    max_regression_pct: float,
) -> Dict[str, Any]:
    view = list(rows[-max(1, int(window)):]) if len(rows) > 0 else []
    total = int(len(view))
    if total <= 0:
        return {
            "pass": True,
            "reason": "no_rows",
            "window_rows": 0,
            "metrics_rows": 0,
            "coverage_pct": 0.0,
            "trend": "n/a",
            "rmse_delta_pct": None,
            "val_loss_delta_pct": None,
            "failed_checks": [],
        }
    q_rows: List[Dict[str, Any]] = []
    for row in view:
        q = _extract_quality_row_from_summary(str(row.get("summary_json", "")))
        if bool(q.get("exists", False)):
            q_rows.append(q)
    metrics_rows = int(len(q_rows))
    coverage = (100.0 * float(metrics_rows) / float(total)) if total > 0 else 0.0
    if total < int(max(1, warmup_cycles)):
        return {
            "pass": True,
            "reason": "warmup",
            "window_rows": int(total),
            "metrics_rows": int(metrics_rows),
            "coverage_pct": float(coverage),
            "trend": "n/a",
            "rmse_delta_pct": None,
            "val_loss_delta_pct": None,
            "failed_checks": [],
        }
    if metrics_rows < int(max(1, min_metrics_rows)):
        return {
            "pass": True,
            "reason": "insufficient_metrics",
            "window_rows": int(total),
            "metrics_rows": int(metrics_rows),
            "coverage_pct": float(coverage),
            "trend": "n/a",
            "rmse_delta_pct": None,
            "val_loss_delta_pct": None,
            "failed_checks": [],
        }

    rmse_vals = [x.get("test_rmse", None) for x in q_rows]
    val_vals = [x.get("best_val_loss", None) for x in q_rows]

    recent_rmse = _mean_opt(rmse_vals[-3:])
    prev_rmse = _mean_opt(rmse_vals[-6:-3] if len(rmse_vals) >= 6 else rmse_vals[:-3])
    recent_val = _mean_opt(val_vals[-3:])
    prev_val = _mean_opt(val_vals[-6:-3] if len(val_vals) >= 6 else val_vals[:-3])

    rmse_delta_pct = _pct_delta_opt(recent_rmse, prev_rmse)
    val_delta_pct = _pct_delta_opt(recent_val, prev_val)

    failed_checks: List[str] = []
    thr = float(max_regression_pct)
    if (rmse_delta_pct is not None) and (float(rmse_delta_pct) > thr):
        failed_checks.append(f"rmse_regression_pct:{float(rmse_delta_pct):.2f}>max:{thr:.2f}")
    if (val_delta_pct is not None) and (float(val_delta_pct) > thr):
        failed_checks.append(f"val_loss_regression_pct:{float(val_delta_pct):.2f}>max:{thr:.2f}")

    trend = "stable"
    if len(failed_checks) > 0:
        trend = "regressing"
    elif ((rmse_delta_pct is not None) and (rmse_delta_pct < -3.0)) or ((val_delta_pct is not None) and (val_delta_pct < -3.0)):
        trend = "improving"

    return {
        "pass": bool(len(failed_checks) == 0),
        "reason": "ok" if len(failed_checks) == 0 else "threshold_miss",
        "window_rows": int(total),
        "metrics_rows": int(metrics_rows),
        "coverage_pct": float(coverage),
        "trend": str(trend),
        "rmse_delta_pct": rmse_delta_pct,
        "val_loss_delta_pct": val_delta_pct,
        "failed_checks": failed_checks,
    }


def _collect_latest_failure_events_from_summaries(
    *,
    out_prefix: str,
    date_tag_prefix: str,
    max_scan_summaries: int,
) -> Dict[str, Any]:
    pattern = f"{str(out_prefix)}_{str(date_tag_prefix)}_*_summary.json"
    files = [x for x in glob.glob(pattern) if os.path.isfile(x)]
    files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    files = files[: max(1, int(max_scan_summaries))]

    latest_by_pid: Dict[str, Dict[str, Any]] = {}
    reason_counts: Dict[str, int] = {}
    event_counts: Dict[str, int] = {}

    for path in files:
        payload = _load_json(path, {})
        if not isinstance(payload, dict):
            continue
        events = payload.get("events", [])
        if not isinstance(events, list):
            continue
        cycle = int(_safe_float(payload.get("cycle", 0), 0))
        date_tag = str(payload.get("date_tag", "")).strip()
        for ev in events:
            if not isinstance(ev, dict):
                continue
            event = str(ev.get("name", "")).strip()
            if event not in ("candidate_failed", "candidate_datagen_error", "candidate_exception", "training_failed"):
                continue
            pid = str(ev.get("protein_id", "")).strip()
            if not pid:
                continue
            reason = str(ev.get("reason", "")).strip() or str(ev.get("error", "")).strip() or event
            category = _classify_failure_category(reason=reason, event=event)
            rec = {
                "protein_id": pid,
                "event": event,
                "reason": reason,
                "category": category,
                "target": str(ev.get("target", "")).strip(),
                "size_mode": str(ev.get("size_mode", "")).strip(),
                "cycle": int(cycle),
                "date_tag": date_tag,
                "summary_json": os.path.abspath(path),
            }
            prev = latest_by_pid.get(pid)
            if (prev is None) or (int(rec["cycle"]) >= int(prev.get("cycle", -1))):
                latest_by_pid[pid] = rec
            reason_counts[reason] = int(reason_counts.get(reason, 0)) + 1
            event_counts[event] = int(event_counts.get(event, 0)) + 1
    return {
        "latest_by_pid": latest_by_pid,
        "reason_counts": reason_counts,
        "event_counts": event_counts,
        "scanned_files": int(len(files)),
    }


def _refresh_failure_backlog_snapshot(
    *,
    args: argparse.Namespace,
    state: Dict[str, Any],
) -> Dict[str, Any]:
    collected = _collect_latest_failure_events_from_summaries(
        out_prefix=str(args.out_prefix),
        date_tag_prefix=str(args.date_tag_prefix),
        max_scan_summaries=int(args.failure_breakdown_max_scan_summaries),
    )
    latest_by_pid = collected.get("latest_by_pid", {}) if isinstance(collected.get("latest_by_pid"), dict) else {}
    proteins = state.get("proteins", {}) if isinstance(state.get("proteins"), dict) else {}
    fail_counts = state.get("fail_counts", {}) if isinstance(state.get("fail_counts"), dict) else {}
    requeue_tracker = state.get("requeue_tracker", {}) if isinstance(state.get("requeue_tracker"), dict) else {}
    failed_ids_raw = [str(x) for x in state.get("failed_protein_ids", []) if str(x).strip()]
    failed_ids: List[str] = []
    stale_pruned_ids: List[str] = []
    for pid in failed_ids_raw:
        rec = proteins.get(pid, {}) if isinstance(proteins.get(pid), dict) else {}
        status = str(rec.get("status", "")).strip().lower()
        if status in {"trained", "deferred_large_cycle"}:
            stale_pruned_ids.append(pid)
            continue
        failed_ids.append(pid)
    if len(stale_pruned_ids) > 0:
        state["failed_protein_ids"] = sorted(set(failed_ids))

    rows: List[Dict[str, Any]] = []
    by_category: Dict[str, int] = {}
    for pid in failed_ids:
        rec = proteins.get(pid, {}) if isinstance(proteins.get(pid), dict) else {}
        lrec = latest_by_pid.get(pid, {}) if isinstance(latest_by_pid.get(pid), dict) else {}
        event = str(rec.get("last_failure_event", "")).strip() or str(lrec.get("event", "")).strip() or "state_failed"
        reason = str(rec.get("last_failure_reason", "")).strip() or str(lrec.get("reason", "")).strip() or str(rec.get("status", "failed"))
        category = str(rec.get("last_failure_category", "")).strip() or _classify_failure_category(reason=reason, event=event)
        row = {
            "protein_id": pid,
            "category": category,
            "event": event,
            "reason": reason,
            "target": str(rec.get("runtime_target", "")).strip() or str(lrec.get("target", "")).strip(),
            "source_target": str(rec.get("source_target", "")).strip(),
            "pdb_id": str(rec.get("pdb_id", "")).strip(),
            "uniprot_id": str(rec.get("uniprot_id", "")).strip(),
            "ca_residues": int(_safe_float(rec.get("ca_residues", 0), 0)),
            "size_mode_last": str(rec.get("size_mode_last", "")).strip(),
            "last_cycle": str(rec.get("last_cycle", "")).strip() or str(lrec.get("date_tag", "")).strip(),
            "fail_count": int(_safe_float(fail_counts.get(pid, 0), 0)),
            "requeue_attempts": int(_safe_float((requeue_tracker.get(pid, {}) if isinstance(requeue_tracker.get(pid), dict) else {}).get("attempts", 0), 0)),
            "summary_json": str(lrec.get("summary_json", "")).strip(),
        }
        rows.append(row)
        by_category[category] = int(by_category.get(category, 0)) + 1

    rows.sort(key=lambda x: (str(x.get("category", "")), -int(x.get("ca_residues", 0)), str(x.get("protein_id", ""))))
    top_categories = sorted(
        [{"category": str(k), "count": int(v)} for k, v in by_category.items()],
        key=lambda x: (-int(x.get("count", 0)), str(x.get("category", ""))),
    )[:10]
    reason_counts_raw = collected.get("reason_counts", {})
    reason_counts = reason_counts_raw if isinstance(reason_counts_raw, dict) else {}
    top_reasons = sorted(
        [{"reason": str(k), "count": int(_safe_float(v, 0))} for k, v in reason_counts.items()],
        key=lambda x: (-int(x.get("count", 0)), str(x.get("reason", ""))),
    )[:10]

    out_json = str(args.failure_breakdown_json)
    out_csv = str(args.failure_breakdown_csv)
    payload = {
        "generated_at_local": _now_local(),
        "state_json": os.path.abspath(str(args.state_json)),
        "history_jsonl": os.path.abspath(str(args.history_jsonl)),
        "failed_total": int(len(failed_ids)),
        "failed_total_raw": int(len(failed_ids_raw)),
        "stale_pruned_count": int(len(stale_pruned_ids)),
        "stale_pruned_ids": stale_pruned_ids[:50],
        "classified_total": int(len(rows)),
        "by_category": by_category,
        "reason_counts": reason_counts,
        "event_counts": collected.get("event_counts", {}),
        "top_categories": top_categories,
        "top_reasons": top_reasons,
        "scanned_summaries": int(collected.get("scanned_files", 0)),
        "rows": rows,
    }
    if bool(args.failure_breakdown_enabled):
        os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
        fields = [
            "protein_id",
            "category",
            "event",
            "reason",
            "target",
            "source_target",
            "pdb_id",
            "uniprot_id",
            "ca_residues",
            "size_mode_last",
            "last_cycle",
            "fail_count",
            "requeue_attempts",
            "summary_json",
        ]
        pd.DataFrame(rows, columns=fields).to_csv(out_csv, index=False)
    state["failure_backlog_summary"] = {
        "generated_at_local": payload["generated_at_local"],
        "failed_total": int(payload["failed_total"]),
        "failed_total_raw": int(payload["failed_total_raw"]),
        "stale_pruned_count": int(payload["stale_pruned_count"]),
        "by_category": by_category,
        "top_categories": top_categories,
        "top_reasons": top_reasons,
        "out_json": os.path.abspath(out_json),
        "out_csv": os.path.abspath(out_csv),
    }
    return payload


def _read_ca_count(pdb_path: str) -> int:
    count = 0
    with open(pdb_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if not line.startswith("ATOM"):
                continue
            atom_name = line[12:16].strip()
            if atom_name == "CA":
                count += 1
    return int(count)


def _box_from_residue_count(n_res: int) -> List[float]:
    if n_res <= 80:
        side = 120.0
    elif n_res <= 160:
        side = 160.0
    else:
        side = 220.0
    return [float(side), float(side), float(side)]


def _register_dynamic_target(target: str, n_res: int) -> None:
    if target in ResearchConstants.CHALLENGES:
        return
    ResearchConstants.CHALLENGES[target] = {
        "n_res": int(n_res),
        "type": "protein",
        "box": _box_from_residue_count(int(n_res)),
        "fold_class": "live_unseen",
    }


def _merge_manifests(base_csv: str, delta_csv: str, out_csv: str) -> Dict[str, Any]:
    frames: List[pd.DataFrame] = []
    base_count = 0
    delta_count = 0
    if str(base_csv).strip() and os.path.exists(base_csv):
        b = pd.read_csv(base_csv)
        base_count = int(b.shape[0])
        frames.append(b)
    if os.path.exists(delta_csv):
        d = pd.read_csv(delta_csv)
        delta_count = int(d.shape[0])
        frames.append(d)
    if not frames:
        pd.DataFrame().to_csv(out_csv, index=False)
        return {"rows_before": 0, "rows_after": 0, "base_rows": 0, "delta_rows": 0, "out_csv": out_csv}
    merged = pd.concat(frames, ignore_index=True)
    rows_before = int(merged.shape[0])
    subset_cols = [c for c in ("target", "split", "output_npz") if c in merged.columns]
    if subset_cols:
        merged = merged.drop_duplicates(subset=subset_cols, keep="last")
    else:
        merged = merged.drop_duplicates(keep="last")
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    merged.to_csv(out_csv, index=False)
    return {
        "rows_before": rows_before,
        "rows_after": int(merged.shape[0]),
        "base_rows": int(base_count),
        "delta_rows": int(delta_count),
        "out_csv": out_csv,
    }


def _extract_best_checkpoint(training_payload: Dict[str, Any]) -> str:
    if not isinstance(training_payload, dict):
        return ""
    result = training_payload.get("result")
    if isinstance(result, dict):
        p = str(result.get("best_checkpoint_path", "")).strip()
        if p and os.path.exists(p):
            return p
    rows = training_payload.get("targets")
    if isinstance(rows, list):
        for row in reversed(rows):
            if not isinstance(row, dict):
                continue
            p = str(row.get("best_checkpoint_path", "")).strip()
            if p and os.path.exists(p):
                return p
    return ""


def _is_transient_training_error(payload: Dict[str, Any]) -> bool:
    if not isinstance(payload, dict):
        return False
    msg = str(payload.get("error", "")).strip().lower()
    if not msg:
        return False
    transient_tokens = (
        "too many open files",
        "dataloader worker process",
        "resource temporarily unavailable",
        "broken pipe",
        "timed out",
    )
    return any(tok in msg for tok in transient_tokens)


def _run_training_job(
    *,
    args: argparse.Namespace,
    cycle_prefix: str,
    date_tag: str,
    state: Dict[str, Any],
    distilled_manifest: str,
    training_target: str,
    seed_offset: int,
    summary_suffix: str,
    log_path: str,
    job_kind: str = "core",
) -> Tuple[bool, Dict[str, Any], str]:
    os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
    payload: Dict[str, Any] = {}
    ok = True
    best_ckpt = ""
    env_backup: Dict[str, Optional[str]] = {}
    env_set: Dict[str, str] = {}
    kind = str(job_kind).strip().lower()
    if kind == "meta":
        # Meta learning can span variable-size proteins; force conservative loader mode.
        env_set = {
            "TRAIN_NUM_WORKERS": "0",
            "TRAIN_PERSISTENT_WORKERS": "0",
            "TRAIN_PREFETCH_FACTOR": "2",
            "TRAIN_BATCH_SIZE": "1",
        }
    else:
        # Long-running loop defaults to low-FD DataLoader settings unless caller overrides.
        if "TRAIN_NUM_WORKERS" not in os.environ:
            env_set["TRAIN_NUM_WORKERS"] = "2"
        if "TRAIN_PERSISTENT_WORKERS" not in os.environ:
            env_set["TRAIN_PERSISTENT_WORKERS"] = "0"
        if "TRAIN_PREFETCH_FACTOR" not in os.environ:
            env_set["TRAIN_PREFETCH_FACTOR"] = "2"
    try:
        for k, v in env_set.items():
            env_backup[k] = os.environ.get(k)
            os.environ[k] = str(v)
        with open(log_path, "a", encoding="utf-8") as io_log:
            with redirect_stdout(io_log), redirect_stderr(io_log):
                payload = run_training_pipeline(
                    target=str(training_target),
                    use_hp_search=bool(args.training_hp_search),
                    schedule=str(args.training_schedule),
                    seed=int(args.seed) + int(seed_offset),
                    max_targets=None if int(args.training_max_targets) <= 0 else int(args.training_max_targets),
                    data_source="distilled",
                    distilled_manifest=str(distilled_manifest),
                    distilled_split_col="split",
                    distilled_min_quality=None,
                    distilled_max_samples_per_shard=None,
                    distilled_sample_weight_col="sampling_weight",
                    distilled_default_shard_weight=1.0,
                    distilled_quality_weight_alpha=0.0,
                    distilled_min_sampling_weight=1e-6,
                    distilled_use_weighted_sampler=True,
                    distilled_weighted_sampler_replacement=True,
                    initial_checkpoint=str(state.get("latest_checkpoint", "")),
                    checkpoint_strict=False,
                    carry_over_checkpoint=False,
                    checkpoint_dir=str(args.checkpoint_dir),
                    early_stop_patience=int(args.training_early_stop_patience),
                    curriculum_summary_json=f"{cycle_prefix}_{summary_suffix}_summary.json",
                    curriculum_summary_csv=f"{cycle_prefix}_{summary_suffix}_summary.csv",
                    run_tag=f"live_unseen_{date_tag}_{summary_suffix}",
                )
        best_ckpt = _extract_best_checkpoint(payload)
    except Exception as exc:
        ok = False
        payload = {"error": str(exc)}
    finally:
        for k, old in env_backup.items():
            if old is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = old
    return bool(ok), payload, str(best_ckpt)


def _poll_meta_async_status(
    *,
    args: argparse.Namespace,
    state: Dict[str, Any],
) -> Dict[str, Any]:
    meta = state.get("meta_async", {}) if isinstance(state.get("meta_async"), dict) else {}
    if not meta:
        return {"enabled": bool(args.meta_async), "running": False, "completed": False}

    pid = int(_safe_float(meta.get("pid", 0), 0))
    started_epoch = float(_safe_float(meta.get("started_epoch_sec", 0.0), 0.0))
    max_runtime = float(max(0.0, float(args.meta_async_max_runtime_sec)))
    result_json = str(meta.get("result_json", "")).strip()
    owner_pid = int(_safe_float(meta.get("owner_pid", 0), 0))

    if pid > 0 and _pid_alive(pid):
        orphan_owner = owner_pid > 0 and (not _pid_alive(owner_pid))
        orphan_no_owner = owner_pid <= 0 and int(_pid_parent(pid)) == 1
        if bool(args.meta_async_kill_orphan) and (orphan_owner or orphan_no_owner):
            try:
                os.kill(pid, signal.SIGKILL)
            except Exception:
                pass
            state["meta_async"] = {}
            state["updated_at_local"] = _now_local()
            _save_state(str(args.state_json), state)
            return {
                "enabled": bool(args.meta_async),
                "running": False,
                "completed": False,
                "orphan_killed": True,
                "pid": int(pid),
                "owner_pid": int(owner_pid),
            }
        if max_runtime > 0.0 and started_epoch > 0.0:
            age = max(0.0, time.time() - started_epoch)
            if age > max_runtime:
                try:
                    os.kill(pid, signal.SIGKILL)
                except Exception:
                    pass
                state["meta_async"] = {}
                state["updated_at_local"] = _now_local()
                _save_state(str(args.state_json), state)
                return {
                    "enabled": bool(args.meta_async),
                    "running": False,
                    "completed": False,
                    "timed_out": True,
                    "pid": int(pid),
                    "age_sec": float(age),
                }
        return {
            "enabled": bool(args.meta_async),
            "running": True,
            "completed": False,
            "pid": int(pid),
        }

    out = _load_json(result_json, {}) if result_json else {}
    payload = out if isinstance(out, dict) else {}
    best_ckpt = str(payload.get("best_checkpoint", "")).strip()
    if best_ckpt:
        state["latest_checkpoint"] = best_ckpt
    state["meta_async"] = {}
    state["updated_at_local"] = _now_local()
    _save_state(str(args.state_json), state)
    return {
        "enabled": bool(args.meta_async),
        "running": False,
        "completed": True,
        "result_json": result_json,
        "result": payload,
    }


def _launch_meta_async(
    *,
    args: argparse.Namespace,
    state: Dict[str, Any],
    cycle_prefix: str,
    date_tag: str,
    distilled_manifest: str,
    seed_offset: int,
    reason: str,
) -> Dict[str, Any]:
    status = _poll_meta_async_status(args=args, state=state)
    if bool(status.get("running", False)):
        return {
            "enabled": bool(args.meta_async),
            "launched": False,
            "reason": "already_running",
            "status": status,
        }

    log_path = f"{cycle_prefix}_meta_async.log"
    out_json = f"{cycle_prefix}_meta_async_result.json"
    payload = {
        "log_path": log_path,
        "out_json": out_json,
        "training_target": str(args.meta_learning_target),
        "training_hp_search": bool(args.training_hp_search),
        "training_schedule": str(args.training_schedule),
        "training_max_targets": int(args.training_max_targets),
        "training_early_stop_patience": int(args.training_early_stop_patience),
        "seed": int(args.seed) + int(seed_offset),
        "distilled_manifest": str(distilled_manifest),
        "initial_checkpoint": str(state.get("latest_checkpoint", "")),
        "checkpoint_dir": str(args.checkpoint_dir),
        "summary_json": f"{cycle_prefix}_meta_async_summary.json",
        "summary_csv": f"{cycle_prefix}_meta_async_summary.csv",
        "run_tag": f"live_unseen_{date_tag}_meta_async",
        "env": {
            "TRAIN_NUM_WORKERS": "0",
            "TRAIN_PERSISTENT_WORKERS": "0",
            "TRAIN_PREFETCH_FACTOR": "2",
            "TRAIN_BATCH_SIZE": "1",
        },
    }
    try:
        ctx = mp.get_context("spawn")
        proc = ctx.Process(target=_meta_learning_worker, args=(payload,))
        proc.start()
    except Exception as exc:
        return {
            "enabled": bool(args.meta_async),
            "launched": False,
            "reason": "spawn_failed",
            "error": str(exc),
            "manifest": str(distilled_manifest),
        }

    state["meta_async"] = {
        "pid": int(proc.pid or 0),
        "owner_pid": int(os.getpid()),
        "started_at_local": _now_local(),
        "started_epoch_sec": float(time.time()),
        "seed_offset": int(seed_offset),
        "reason": str(reason),
        "manifest": str(distilled_manifest),
        "result_json": str(out_json),
        "log_path": str(log_path),
    }
    state["updated_at_local"] = _now_local()
    _save_state(str(args.state_json), state)
    return {
        "enabled": bool(args.meta_async),
        "launched": True,
        "pid": int(proc.pid or 0),
        "reason": str(reason),
        "manifest": str(distilled_manifest),
        "result_json": str(out_json),
        "log_path": str(log_path),
    }


def _parse_csv_like_list(raw: str) -> List[str]:
    return [x.strip() for x in str(raw).split(",") if x.strip()]


def _derive_failure_requeue_adaptive_policy(
    *,
    args: argparse.Namespace,
    state: Dict[str, Any],
) -> Dict[str, Any]:
    base_categories = [str(x).strip().lower() for x in _parse_csv_like_list(str(getattr(args, "failure_requeue_categories", "")))]
    base_set = set(x for x in base_categories if x)

    enabled = bool(getattr(args, "failure_adaptive_requeue_enabled", True))
    min_count = int(max(1, int(getattr(args, "failure_adaptive_min_count", 2))))
    extra_retries = int(max(0, int(getattr(args, "failure_adaptive_extra_retries", 1))))
    cooldown_reduction = int(max(0, int(getattr(args, "failure_adaptive_cooldown_reduction", 1))))

    hot_allow_raw = [str(x).strip().lower() for x in _parse_csv_like_list(str(getattr(args, "failure_adaptive_hot_categories", "")))]
    hot_allow = set(x for x in hot_allow_raw if x)
    transient_raw = [str(x).strip().lower() for x in _parse_csv_like_list(str(getattr(args, "failure_adaptive_transient_categories", "")))]
    transient = set(x for x in transient_raw if x)

    by_category = (
        state.get("failure_backlog_summary", {}).get("by_category", {})
        if isinstance(state.get("failure_backlog_summary", {}), dict)
        else {}
    )
    if not isinstance(by_category, dict):
        by_category = {}
    hot_categories: List[str] = []
    if enabled:
        ranked = sorted(
            ((str(k).strip().lower(), int(_safe_float(v, 0))) for k, v in by_category.items()),
            key=lambda kv: (-int(kv[1]), str(kv[0])),
        )
        for cat, cnt in ranked:
            if (not cat) or int(cnt) < int(min_count):
                continue
            if hot_allow and cat not in hot_allow:
                continue
            hot_categories.append(cat)

    effective = sorted(base_set.union(set(hot_categories)))
    base_retry = int(max(0, int(getattr(args, "failure_requeue_max_retries", 2))))
    base_cooldown = int(max(0, int(getattr(args, "failure_requeue_cooldown_cycles", 3))))
    retry_caps: Dict[str, int] = {}
    cooldown_cycles: Dict[str, int] = {}
    for cat in hot_categories:
        if cat in transient:
            retry_caps[cat] = int(max(0, base_retry + extra_retries))
            cooldown_cycles[cat] = int(max(0, base_cooldown - cooldown_reduction))
        else:
            retry_caps[cat] = int(base_retry)
            cooldown_cycles[cat] = int(base_cooldown)

    return {
        "enabled": bool(enabled),
        "base_categories": sorted(base_set),
        "hot_categories": hot_categories,
        "effective_categories": effective,
        "retry_caps": retry_caps,
        "cooldown_cycles": cooldown_cycles,
        "min_count": int(min_count),
        "extra_retries": int(extra_retries),
        "cooldown_reduction": int(cooldown_reduction),
    }


def _read_list_file(path: str) -> List[str]:
    if (not str(path).strip()) or (not os.path.exists(path)):
        return []
    out: List[str] = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            s = str(line).strip()
            if (not s) or s.startswith("#"):
                continue
            out.append(s)
    return out


def _discover_latest_files_by_patterns(patterns: Sequence[str], max_per_pattern: int = 2) -> List[str]:
    found: List[str] = []
    for pat in patterns:
        p = str(pat).strip()
        if not p:
            continue
        rows = [x for x in glob.glob(p) if os.path.isfile(x)]
        rows.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        found.extend(rows[: max(1, int(max_per_pattern))])
    uniq: List[str] = []
    seen: set[str] = set()
    for x in found:
        ap = os.path.abspath(x)
        if ap in seen:
            continue
        seen.add(ap)
        uniq.append(ap)
    return uniq


def _extract_cycle_key_from_name(path: str, out_prefix: str, date_tag_prefix: str) -> str:
    base = os.path.basename(path)
    pref = f"{os.path.basename(out_prefix)}_{date_tag_prefix}_"
    if not base.startswith(pref):
        return ""
    tail = base[len(pref):]
    m = re.match(r"(\d{3,})_(\d{6})", tail)
    if not m:
        return ""
    return f"{m.group(1)}_{m.group(2)}"


def _cleanup_old_cycle_artifacts(
    *,
    out_prefix: str,
    date_tag_prefix: str,
    keep_recent_cycles: int,
    dry_run: bool,
    compress_to_archive: bool = False,
    archive_dir: str = "archives/live_unseen_runs",
    delete_after_archive: bool = True,
) -> Dict[str, Any]:
    if int(keep_recent_cycles) <= 0:
        return {"enabled": False, "removed_files": 0}
    pattern = f"{out_prefix}_{date_tag_prefix}_*"
    files = [p for p in glob.glob(pattern) if os.path.isfile(p)]
    ranked: List[Tuple[int, int, float, str, str]] = []
    for fp in files:
        ckey = _extract_cycle_key_from_name(fp, out_prefix=out_prefix, date_tag_prefix=date_tag_prefix)
        seq = -1
        hhmmss = -1
        if ckey:
            parts = ckey.split("_")
            if len(parts) == 2:
                seq = int(_safe_float(parts[0], -1))
                hhmmss = int(_safe_float(parts[1], -1))
        ranked.append((seq, hhmmss, float(os.path.getmtime(fp)), ckey, fp))
    ranked.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
    keep_keys: List[str] = []
    keep_set: set[str] = set()
    removed: List[str] = []
    to_archive_by_key: Dict[str, List[str]] = {}
    for _seq, _hhmmss, _mtime, ckey, fp in ranked:
        if not ckey:
            continue
        if (ckey not in keep_set) and (len(keep_keys) < int(keep_recent_cycles)):
            keep_keys.append(ckey)
            keep_set.add(ckey)
            continue
        if ckey in keep_set:
            continue
        if bool(compress_to_archive):
            to_archive_by_key.setdefault(ckey, []).append(fp)
        else:
            removed.append(fp)
            if not bool(dry_run):
                try:
                    os.unlink(fp)
                except Exception:
                    pass

    archived: List[str] = []
    archived_files = 0
    archive_errors: List[Dict[str, Any]] = []
    if bool(compress_to_archive) and len(to_archive_by_key) > 0:
        archive_root = os.path.abspath(str(archive_dir))
        prefix_base = f"{os.path.basename(out_prefix)}_{date_tag_prefix}"
        for ckey, files_for_key in sorted(to_archive_by_key.items()):
            if len(files_for_key) == 0:
                continue
            arc_name = f"{prefix_base}_{ckey}.tar.gz"
            arc_path = os.path.join(archive_root, arc_name)
            if os.path.exists(arc_path):
                idx = 2
                while os.path.exists(arc_path):
                    arc_path = os.path.join(archive_root, f"{prefix_base}_{ckey}__{idx}.tar.gz")
                    idx += 1
            try:
                if not bool(dry_run):
                    os.makedirs(archive_root, exist_ok=True)
                    with tarfile.open(arc_path, mode="w:gz") as tar:
                        for fp in files_for_key:
                            if os.path.exists(fp):
                                tar.add(fp, arcname=os.path.basename(fp))
                archived.append(arc_path)
                archived_files += int(len(files_for_key))
                if bool(delete_after_archive):
                    for fp in files_for_key:
                        removed.append(fp)
                        if not bool(dry_run):
                            try:
                                os.unlink(fp)
                            except Exception:
                                pass
            except Exception as exc:
                archive_errors.append(
                    {
                        "cycle_key": ckey,
                        "archive_path": arc_path,
                        "error": str(exc),
                        "file_count": int(len(files_for_key)),
                    }
                )
    return {
        "enabled": True,
        "pattern": pattern,
        "scanned_files": int(len(ranked)),
        "keep_recent_cycles": int(keep_recent_cycles),
        "kept_cycle_keys": keep_keys,
        "compress_to_archive": bool(compress_to_archive),
        "archive_dir": os.path.abspath(str(archive_dir)),
        "delete_after_archive": bool(delete_after_archive),
        "archived_files": int(archived_files),
        "archive_count": int(len(archived)),
        "archive_examples": archived[:20],
        "archive_errors": archive_errors[:20],
        "removed_files": int(len(removed)),
        "removed_examples": removed[:20],
    }


def _safe_rmtree(path: str) -> bool:
    try:
        if str(path).strip() and os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
            return True
    except Exception:
        return False
    return False

def _select_best_structure_path(fetch_df: pd.DataFrame, target: str) -> str:
    if fetch_df.empty:
        return ""
    sub = fetch_df[fetch_df["target"].astype(str) == str(target)].copy()
    if sub.empty:
        return ""
    if "status" in sub.columns:
        sub = sub[sub["status"].astype(str).isin(["downloaded", "exists"])]
    if sub.empty:
        return ""
    kind = sub["source_kind"].astype(str).str.lower() if "source_kind" in sub.columns else pd.Series([""] * len(sub))
    status = sub["status"].astype(str).str.lower() if "status" in sub.columns else pd.Series([""] * len(sub))
    sub["kind_rank"] = kind.map(lambda x: 0 if x.startswith("afdb") else 1)
    sub["status_rank"] = status.map(lambda x: 0 if x == "downloaded" else 1)
    sub = sub.sort_values(by=["kind_rank", "status_rank"])
    best = sub.iloc[0]
    p = str(best.get("path", "")).strip()
    return p if p and os.path.exists(p) else ""


def _prepare_candidates(
    sources_df: pd.DataFrame,
    state: Dict[str, Any],
    limit: int,
    max_failures: int,
    cycle_idx: int,
    policy: str,
    small_ca_threshold: int,
    medium_ca_threshold: int,
    include_large_every_cycles: int,
    include_large_probe_on_non_large_cycle: bool,
    oversize_recovery_if_idle: bool,
    oversize_recovery_topk: int,
    large_loop_enabled: bool,
    failure_requeue_enabled: bool,
    failure_requeue_max_retries: int,
    failure_requeue_cooldown_cycles: int,
    failure_requeue_categories: Sequence[str],
    failure_requeue_retry_caps: Optional[Dict[str, int]] = None,
    failure_requeue_cooldown_by_category: Optional[Dict[str, int]] = None,
) -> List[Dict[str, Any]]:
    if sources_df.empty:
        return []
    trained = set(str(x) for x in state.get("trained_protein_ids", []))
    fail_counts = state.get("fail_counts", {}) if isinstance(state.get("fail_counts"), dict) else {}
    proteins = state.get("proteins", {}) if isinstance(state.get("proteins"), dict) else {}
    requeue_tracker = state.get("requeue_tracker", {}) if isinstance(state.get("requeue_tracker"), dict) else {}
    requeue_cats = set(str(x).strip().lower() for x in failure_requeue_categories if str(x).strip())
    requeue_retry_caps = failure_requeue_retry_caps if isinstance(failure_requeue_retry_caps, dict) else {}
    requeue_cooldown_caps = (
        failure_requeue_cooldown_by_category if isinstance(failure_requeue_cooldown_by_category, dict) else {}
    )
    oversize_idle_enabled = bool(oversize_recovery_if_idle)
    oversize_idle_topk = int(max(1, oversize_recovery_topk))
    large_cycle_active = int(include_large_every_cycles) > 0 and (int(cycle_idx) % int(include_large_every_cycles) == 0)

    rows: List[Dict[str, Any]] = []
    for rec in sources_df.to_dict(orient="records"):
        target = str(rec.get("target", "")).strip()
        pdb_id = str(rec.get("pdb_id", "")).strip().upper()
        uniprot_id = str(rec.get("uniprot_id", "")).strip().upper()
        protein_id = _compose_protein_id(target=target, pdb_id=pdb_id, uniprot_id=uniprot_id)
        if protein_id in trained:
            continue
        p_rec = proteins.get(protein_id, {}) if isinstance(proteins.get(protein_id, {}), dict) else {}
        n_fail = int(fail_counts.get(protein_id, 0))
        requeue_override = False
        requeue_category = ""
        requeue_attempts = 0
        if n_fail >= int(max_failures):
            if not bool(failure_requeue_enabled):
                continue
            reason = str(p_rec.get("last_failure_reason", "")).strip()
            event = str(p_rec.get("last_failure_event", "")).strip()
            category = str(p_rec.get("last_failure_category", "")).strip().lower() or _classify_failure_category(reason=reason, event=event)
            if category not in requeue_cats:
                continue
            if category == "oversize_hard_cap":
                continue
            if category in {"oversize", "oversize_wait_large_cycle"}:
                if not bool(large_loop_enabled):
                    continue
                if not bool(large_cycle_active):
                    if not bool(oversize_idle_enabled):
                        continue
            t_rec = requeue_tracker.get(protein_id, {}) if isinstance(requeue_tracker.get(protein_id, {}), dict) else {}
            attempts = int(_safe_float(t_rec.get("attempts", 0), 0))
            last_cycle_i = int(_safe_float(t_rec.get("last_cycle", -1000000), -1000000))
            retry_cap = int(max(0, int(requeue_retry_caps.get(category, failure_requeue_max_retries))))
            cooldown_cap = int(max(0, int(requeue_cooldown_caps.get(category, failure_requeue_cooldown_cycles))))
            if attempts >= int(retry_cap):
                continue
            if (int(cycle_idx) - int(last_cycle_i)) < int(cooldown_cap):
                continue
            requeue_override = True
            requeue_category = str(category)
            requeue_attempts = int(attempts)
            requeue_retry_cap = int(retry_cap)
            requeue_cooldown_cycles = int(cooldown_cap)
        else:
            requeue_retry_cap = int(max(0, int(failure_requeue_max_retries)))
            requeue_cooldown_cycles = int(max(0, int(failure_requeue_cooldown_cycles)))
        row = dict(rec)
        row["target"] = target
        row["pdb_id"] = pdb_id
        row["uniprot_id"] = uniprot_id
        row["protein_id"] = protein_id
        row["runtime_target"] = _runtime_target_name(row)
        try:
            row["priority"] = float(rec.get("priority", 0.0))
        except Exception:
            row["priority"] = 0.0
        ca_hint = int(_safe_float(p_rec.get("ca_residues", p_rec.get("ca_residues_hint", 0)), 0))
        row["ca_residues_hint"] = int(max(ca_hint, 0))
        row["requeue_override"] = bool(requeue_override)
        row["requeue_category"] = str(requeue_category)
        row["oversize_recovery_only"] = bool(requeue_category in {"oversize", "oversize_wait_large_cycle"} and not bool(large_cycle_active))
        row["requeue_attempts"] = int(requeue_attempts)
        row["requeue_retry_cap"] = int(requeue_retry_cap)
        row["requeue_cooldown_cycles"] = int(requeue_cooldown_cycles)
        rows.append(row)
    rows.sort(
        key=lambda r: (
            0 if bool(r.get("requeue_override", False)) else 1,
            -float(r.get("priority", 0.0)),
            str(r.get("protein_id", "")),
        )
    )

    policy_i = str(policy).strip().lower()
    if policy_i != "size_curriculum":
        limit_i = max(int(limit), 0)
        picked = rows[:limit_i]
        if bool(oversize_idle_enabled) and len(picked) <= 0:
            recovery_rows = [r for r in rows if bool(r.get("oversize_recovery_only", False))]
            return recovery_rows[: min(limit_i if limit_i > 0 else oversize_idle_topk, oversize_idle_topk)]
        return picked

    small_max = int(max(1, small_ca_threshold))
    medium_max = int(max(small_max, medium_ca_threshold))
    large_every = int(max(0, include_large_every_cycles))

    small: List[Dict[str, Any]] = []
    medium: List[Dict[str, Any]] = []
    unknown: List[Dict[str, Any]] = []
    large: List[Dict[str, Any]] = []
    for row in rows:
        hint = int(row.get("ca_residues_hint", 0))
        if hint <= 0:
            unknown.append(row)
            continue
        if hint <= small_max:
            small.append(row)
            continue
        if hint <= medium_max:
            medium.append(row)
            continue
        large.append(row)

    ordered: List[Dict[str, Any]] = []
    ordered.extend(small)
    ordered.extend(medium)
    ordered.extend(unknown)
    if len(large) > 0:
        if large_every > 0 and (int(cycle_idx) % int(large_every) == 0):
            ordered.extend(large)
        elif bool(include_large_probe_on_non_large_cycle):
            # Optional probe candidate on non-large cycles.
            ordered.extend(large[:1])
    limit_i = max(int(limit), 0)
    selected = ordered[:limit_i]
    if bool(oversize_idle_enabled) and len(selected) <= 0:
        recovery_rows = [r for r in rows if bool(r.get("oversize_recovery_only", False))]
        if len(recovery_rows) > 0:
            selected = recovery_rows[: min(limit_i if limit_i > 0 else oversize_idle_topk, oversize_idle_topk)]
    return selected


def _ingest_md_artifact(
    md_df: pd.DataFrame,
    candidate: Dict[str, Any],
    out_dir: str,
    timeout_sec: float,
    dry_run: bool,
) -> Dict[str, Any]:
    if md_df.empty:
        return {"matched": False}
    protein_id = str(candidate.get("protein_id", ""))
    target = str(candidate.get("target", ""))
    uniprot = str(candidate.get("uniprot_id", ""))
    pdb_id = str(candidate.get("pdb_id", ""))
    best: Optional[Dict[str, Any]] = None
    for rec in md_df.to_dict(orient="records"):
        rid = _compose_protein_id(
            target=str(rec.get("target", "")),
            pdb_id=str(rec.get("pdb_id", "")),
            uniprot_id=str(rec.get("uniprot_id", "")),
        )
        if rid == protein_id:
            best = rec
            break
        if str(rec.get("target", "")).strip() == target and target:
            best = rec
            break
        if str(rec.get("uniprot_id", "")).strip().upper() == uniprot and uniprot:
            best = rec
            break
        if str(rec.get("pdb_id", "")).strip().upper() == pdb_id and pdb_id:
            best = rec
            break
    if best is None:
        return {"matched": False}
    md_path = str(best.get("md_path", "")).strip()
    md_url = str(best.get("md_url", "")).strip()
    label = str(best.get("label", "")).strip()
    if md_path and os.path.exists(md_path):
        return {"matched": True, "ok": True, "path": os.path.abspath(md_path), "label": label, "from": "local_path"}
    if md_url:
        os.makedirs(out_dir, exist_ok=True)
        out_file = os.path.join(out_dir, f"{_slug(candidate.get('runtime_target', protein_id))}_md.bin")
        if dry_run:
            return {"matched": True, "ok": True, "path": os.path.abspath(out_file), "label": label, "from": "dry_run"}
        dl = _download_file(md_url, out_file, timeout_sec=timeout_sec)
        return {"matched": True, "ok": bool(dl.get("ok", False)), "path": dl.get("path", out_file), "label": label, "from": "url", "error": dl.get("error", "")}
    return {"matched": True, "ok": False, "path": "", "label": label, "error": "md_path_or_md_url_missing"}


def _run_openmm_reference(
    target: str,
    date_tag: str,
    out_dir: str,
    steps: int,
    save_stride: int,
    strict: bool,
) -> Dict[str, Any]:
    try:
        from tools import generate_openmm_ca_md_references as openmm_ref  # local import for optional dependency
    except Exception as exc:
        return {"ok": False, "error": f"openmm_import_failed:{exc}"}

    out_manifest = os.path.join(out_dir, f"openmm_live_unseen_{_slug(target)}_{date_tag}.csv")
    out_json = os.path.join(out_dir, f"openmm_live_unseen_{_slug(target)}_{date_tag}.json")
    args = openmm_ref.build_parser().parse_args([])
    args.targets = str(target)
    args.out_dir = out_dir
    args.out_manifest = out_manifest
    args.out_json = out_json
    args.representation = "ca_sc_2bead"
    args.steps = int(steps)
    args.save_stride = int(save_stride)
    try:
        payload = openmm_ref.generate_openmm_ca_md_references(args)
        return {
            "ok": True,
            "out_manifest": out_manifest,
            "out_json": out_json,
            "target_count": int(payload.get("summary", {}).get("target_count", 0)),
        }
    except Exception as exc:
        if strict:
            raise
        return {"ok": False, "error": str(exc), "out_manifest": out_manifest, "out_json": out_json}


@dataclass
class CycleResult:
    cycle: int
    date_tag: str
    pass_flag: bool
    core_pass: bool
    meta_pass: Optional[bool]
    trained_ids: List[str]
    failed_ids: List[str]
    summary_json: str


def _run_cycle(args: argparse.Namespace, cycle_idx: int, state: Dict[str, Any]) -> CycleResult:
    date_tag = f"{args.date_tag_prefix}_{cycle_idx:03d}_{dt.datetime.now().strftime('%H%M%S')}"
    cycle_prefix = f"{args.out_prefix}_{date_tag}"
    cycle_summary_json = f"{cycle_prefix}_summary.json"
    cycle_events: List[Dict[str, Any]] = []
    cycle_datagen_log = f"{cycle_prefix}_datagen.log"
    cycle_training_log = f"{cycle_prefix}_training.log"
    _update_runtime_state(
        args=args,
        state=state,
        cycle_idx=int(cycle_idx),
        date_tag=str(date_tag),
        phase="cycle_start",
        current_target="",
        note="cycle_started",
        persist=True,
    )

    meta_poll = _poll_meta_async_status(args=args, state=state)
    if bool(meta_poll.get("completed", False)):
        cycle_events.append({"name": "meta_learning_async_result", "payload": meta_poll})
    if bool(meta_poll.get("timed_out", False)):
        cycle_events.append({"name": "meta_learning_async_timeout", "payload": meta_poll})

    _update_runtime_state(
        args=args,
        state=state,
        cycle_idx=int(cycle_idx),
        date_tag=str(date_tag),
        phase="refresh_sources",
        note="source_refresh",
        persist=True,
    )
    refresh_sources = _refresh_csv_from_url(
        url=str(args.sources_url),
        out_csv=str(args.sources_csv),
        timeout_sec=float(args.timeout_sec),
    )
    cycle_events.append({"name": "refresh_sources", "payload": refresh_sources})
    ensure_sources_payload = _ensure_sources_csv(str(args.sources_csv))
    cycle_events.append({"name": "ensure_sources_csv", "payload": ensure_sources_payload})

    refresh_md = _refresh_csv_from_url(
        url=str(args.md_sources_url),
        out_csv=str(args.md_sources_csv),
        timeout_sec=float(args.timeout_sec),
    ) if str(args.md_sources_url).strip() else {"refreshed": False}
    cycle_events.append({"name": "refresh_md_sources", "payload": refresh_md})
    ensure_md_sources_payload = _ensure_md_sources_csv(str(args.md_sources_csv))
    cycle_events.append({"name": "ensure_md_sources_csv", "payload": ensure_md_sources_payload})

    _update_runtime_state(
        args=args,
        state=state,
        cycle_idx=int(cycle_idx),
        date_tag=str(date_tag),
        phase="afdb_sync",
        note="auto_sync",
        persist=True,
    )
    auto_sync_payload = {"enabled": False}
    if bool(args.auto_sync_afdb_candidates):
        no_add_cycles_before = int(_safe_float(state.get("afdb_no_add_cycles", 0), 0))
        afdb_cursor_before = str(state.get("afdb_query_cursor", "") or "").strip()
        base_query_size = max(1, int(args.afdb_query_size))
        effective_query_size = base_query_size
        if bool(args.afdb_query_autogrow) and no_add_cycles_before > 0:
            grow = 1 + int(no_add_cycles_before)
            effective_query_size = min(
                max(1, int(args.afdb_query_autogrow_max_size)),
                base_query_size * grow,
            )
        auto_sync_started = time.perf_counter()
        try:
            auto_sync_payload = _auto_sync_afdb_sources(
                sources_csv=str(args.sources_csv),
                state=state,
                cache_json=str(args.afdb_score_cache_json),
                query=str(args.afdb_uniprot_query),
                query_size=int(effective_query_size),
                min_global_metric=float(args.afdb_min_global_metric),
                add_per_cycle=int(args.afdb_add_per_cycle),
                timeout_sec=float(args.timeout_sec),
                max_metric_lookups_per_cycle=int(args.afdb_max_metric_lookups_per_cycle),
                start_cursor=str(afdb_cursor_before),
                pages_per_cycle=int(args.afdb_pages_per_cycle),
                reset_cursor_on_empty=bool(args.afdb_reset_cursor_on_empty),
            )
            added_now = int(_safe_float(auto_sync_payload.get("added_rows", 0), 0))
            state["afdb_no_add_cycles"] = 0 if added_now > 0 else int(no_add_cycles_before + 1)
            state["afdb_query_cursor"] = str(auto_sync_payload.get("query_cursor_out", "") or "")
            auto_sync_payload["base_query_size"] = int(base_query_size)
            auto_sync_payload["effective_query_size"] = int(effective_query_size)
            auto_sync_payload["no_add_cycles_before"] = int(no_add_cycles_before)
            auto_sync_payload["no_add_cycles_after"] = int(state.get("afdb_no_add_cycles", 0))
            auto_sync_payload["query_cursor_before"] = str(afdb_cursor_before)
            auto_sync_payload["query_cursor_after"] = str(state.get("afdb_query_cursor", ""))
            auto_sync_payload["ok"] = bool(auto_sync_payload.get("ok", True))
        except Exception as exc:
            auto_sync_payload = {"enabled": True, "ok": False, "error": str(exc)}
            state["afdb_no_add_cycles"] = int(no_add_cycles_before + 1)
        auto_sync_payload["elapsed_sec"] = float(max(0.0, time.perf_counter() - float(auto_sync_started)))
    cycle_events.append({"name": "auto_sync_afdb_sources", "payload": auto_sync_payload})

    md_catalog_urls = _parse_csv_like_list(str(args.md_catalog_urls))
    md_catalog_urls.extend(_read_list_file(str(args.md_catalog_urls_file)))
    if bool(args.auto_discover_local_md_catalogs):
        local_patterns = _parse_csv_like_list(str(args.local_md_catalog_globs))
        md_catalog_urls.extend(
            _discover_latest_files_by_patterns(
                patterns=local_patterns,
                max_per_pattern=int(args.local_md_catalog_max_per_glob),
            )
        )
    md_catalog_urls = [x for i, x in enumerate(md_catalog_urls) if x and x not in md_catalog_urls[:i]]
    md_catalog_sync = {"enabled": False}
    if len(md_catalog_urls) > 0:
        try:
            md_catalog_sync = _sync_md_sources_from_catalog_urls(
                md_sources_csv=str(args.md_sources_csv),
                catalog_urls=md_catalog_urls,
                timeout_sec=float(args.timeout_sec),
            )
        except Exception as exc:
            md_catalog_sync = {"enabled": True, "ok": False, "error": str(exc), "catalog_urls": md_catalog_urls}
    cycle_events.append({"name": "sync_md_sources_from_catalogs", "payload": md_catalog_sync})

    _update_runtime_state(
        args=args,
        state=state,
        cycle_idx=int(cycle_idx),
        date_tag=str(date_tag),
        phase="candidate_select",
        note="prepare_candidates",
        persist=True,
    )
    sources_df = _read_csv_if_exists(str(args.sources_csv))
    md_df = _read_csv_if_exists(str(args.md_sources_csv))
    adaptive_requeue_policy = _derive_failure_requeue_adaptive_policy(args=args, state=state)
    state["failure_requeue_policy"] = adaptive_requeue_policy
    requeue_categories = (
        adaptive_requeue_policy.get("effective_categories", [])
        if bool(adaptive_requeue_policy.get("enabled", False))
        else _parse_csv_like_list(str(args.failure_requeue_categories))
    )
    cycle_events.append(
        {
            "name": "failure_requeue_policy",
            "payload": {
                "enabled": bool(adaptive_requeue_policy.get("enabled", False)),
                "hot_categories": adaptive_requeue_policy.get("hot_categories", []),
                "effective_categories": requeue_categories,
                "retry_caps": adaptive_requeue_policy.get("retry_caps", {}),
                "cooldown_cycles": adaptive_requeue_policy.get("cooldown_cycles", {}),
            },
        }
    )
    candidates = _prepare_candidates(
        sources_df=sources_df,
        state=state,
        limit=int(args.new_proteins_per_cycle),
        max_failures=int(args.max_failures_per_protein),
        cycle_idx=int(cycle_idx),
        policy=str(args.candidate_order_policy),
        small_ca_threshold=int(args.small_ca_threshold),
        medium_ca_threshold=int(args.medium_ca_threshold),
        include_large_every_cycles=int(args.include_large_every_cycles),
        include_large_probe_on_non_large_cycle=bool(args.include_large_probe_on_non_large_cycle),
        oversize_recovery_if_idle=bool(args.oversize_recovery_if_idle),
        oversize_recovery_topk=int(args.oversize_recovery_topk),
        large_loop_enabled=bool(args.large_loop_enabled),
        failure_requeue_enabled=bool(args.failure_requeue_enabled),
        failure_requeue_max_retries=int(args.failure_requeue_max_retries),
        failure_requeue_cooldown_cycles=int(args.failure_requeue_cooldown_cycles),
        failure_requeue_categories=requeue_categories,
        failure_requeue_retry_caps=adaptive_requeue_policy.get("retry_caps", {}),
        failure_requeue_cooldown_by_category=adaptive_requeue_policy.get("cooldown_cycles", {}),
    )
    requeue_tracker = state.get("requeue_tracker", {}) if isinstance(state.get("requeue_tracker"), dict) else {}
    requeue_selected: List[Dict[str, Any]] = []
    for c in candidates:
        if not bool(c.get("requeue_override", False)):
            continue
        pid = str(c.get("protein_id", "")).strip()
        if not pid:
            continue
        t_rec = requeue_tracker.get(pid, {}) if isinstance(requeue_tracker.get(pid, {}), dict) else {}
        attempts = int(_safe_float(t_rec.get("attempts", 0), 0)) + 1
        t_rec["attempts"] = int(attempts)
        t_rec["last_cycle"] = int(cycle_idx)
        t_rec["last_date_tag"] = str(date_tag)
        t_rec["category"] = str(c.get("requeue_category", "")).strip()
        t_rec["updated_at_local"] = _now_local()
        requeue_tracker[pid] = t_rec
        requeue_selected.append(
            {
                "protein_id": pid,
                "category": str(c.get("requeue_category", "")).strip(),
                "attempts": int(attempts),
                "retry_cap": int(_safe_float(c.get("requeue_retry_cap", args.failure_requeue_max_retries), args.failure_requeue_max_retries)),
                "cooldown_cycles": int(_safe_float(c.get("requeue_cooldown_cycles", args.failure_requeue_cooldown_cycles), args.failure_requeue_cooldown_cycles)),
            }
        )
    state["requeue_tracker"] = requeue_tracker
    if len(requeue_selected) > 0:
        cycle_events.append(
            {
                "name": "failure_requeue_selected",
                "payload": {
                    "count": int(len(requeue_selected)),
                    "rows": requeue_selected[:20],
                },
            }
        )
    oversize_recovery_selected = [
        {
            "protein_id": str(c.get("protein_id", "")),
            "category": str(c.get("requeue_category", "")),
            "ca_residues_hint": int(_safe_float(c.get("ca_residues_hint", 0), 0)),
        }
        for c in candidates
        if bool(c.get("oversize_recovery_only", False))
    ]
    if len(oversize_recovery_selected) > 0:
        cycle_events.append(
            {
                "name": "oversize_recovery_selected",
                "payload": {
                    "count": int(len(oversize_recovery_selected)),
                    "rows": oversize_recovery_selected[:20],
                },
            }
        )
    if len(candidates) == 0:
        idle_meta_payload: Dict[str, Any] = {"enabled": False}
        idle_meta_ok = True
        if bool(args.run_training) and bool(args.run_meta_learning_when_idle):
            every = int(args.meta_learning_every_cycles)
            if every > 0 and (int(cycle_idx) % every == 0):
                manifest_for_idle = ""
                if str(args.base_manifest_csv).strip() and os.path.exists(str(args.base_manifest_csv)):
                    manifest_for_idle = str(args.base_manifest_csv)
                elif str(args.live_manifest_csv).strip() and os.path.exists(str(args.live_manifest_csv)):
                    manifest_for_idle = str(args.live_manifest_csv)
                if manifest_for_idle:
                    if bool(args.meta_async):
                        idle_meta_payload = _launch_meta_async(
                            args=args,
                            state=state,
                            cycle_prefix=cycle_prefix,
                            date_tag=date_tag,
                            distilled_manifest=manifest_for_idle,
                            seed_offset=int(cycle_idx) + 700000,
                            reason="idle",
                        )
                        idle_meta_ok = bool(idle_meta_payload.get("launched", False) or idle_meta_payload.get("status"))
                    else:
                        meta_ok, meta_payload, meta_ckpt = _run_training_job(
                            args=args,
                            cycle_prefix=cycle_prefix,
                            date_tag=date_tag,
                            state=state,
                            distilled_manifest=manifest_for_idle,
                            training_target=str(args.meta_learning_target),
                            seed_offset=int(cycle_idx) + 700000,
                            summary_suffix="meta_idle",
                            log_path=f"{cycle_prefix}_meta_idle.log",
                            job_kind="meta",
                        )
                        idle_meta_ok = bool(meta_ok)
                        idle_meta_payload = {
                            "enabled": True,
                            "ok": bool(meta_ok),
                            "manifest": manifest_for_idle,
                            "training_payload": meta_payload,
                        }
                        if meta_ckpt:
                            state["latest_checkpoint"] = str(meta_ckpt)
                        if not idle_meta_ok:
                            idle_meta_payload["non_blocking"] = True
                            idle_meta_payload["transient_error"] = bool(_is_transient_training_error(meta_payload))
                            cycle_events.append(
                                {
                                    "name": "meta_learning_idle_non_blocking_failure",
                                    "payload": idle_meta_payload,
                                }
                            )
                else:
                    idle_meta_payload = {"enabled": True, "ok": True, "skipped": True, "reason": "no_manifest_available"}
        cycle_events.append({"name": "meta_learning_idle", "payload": idle_meta_payload})

        cleanup_payload = {"enabled": False}
        if bool(args.cleanup_enabled):
            cleanup_payload = _cleanup_old_cycle_artifacts(
                out_prefix=str(args.out_prefix),
                date_tag_prefix=str(args.date_tag_prefix),
                keep_recent_cycles=int(args.cleanup_keep_recent_cycles),
                dry_run=bool(args.dry_run),
                compress_to_archive=bool(args.cleanup_compress_runs_artifacts),
                archive_dir=str(args.cleanup_archive_dir),
                delete_after_archive=bool(args.cleanup_delete_after_archive),
            )
        cycle_events.append({"name": "cleanup_old_cycle_artifacts", "payload": cleanup_payload})

        payload = {
            "generated_at_local": _now_local(),
            "date_tag": date_tag,
            "cycle": int(cycle_idx),
            "pass": True,
            "core_pass": True,
            "meta_pass": bool(idle_meta_ok) if bool(idle_meta_payload.get("enabled", False)) else None,
            "reason": "no_unseen_candidates",
            "candidates_selected": 0,
            "trained_ids": [],
            "failed_ids": [],
            "source_rows": int(sources_df.shape[0]) if not sources_df.empty else 0,
            "md_source_rows": int(md_df.shape[0]) if not md_df.empty else 0,
            "afdb_sync_elapsed_sec": float(_safe_float(auto_sync_payload.get("elapsed_sec", 0.0), 0.0)),
            "train_throughput_samples_per_sec_last": None,
            "train_throughput_samples_per_sec_avg": None,
            "train_throughput_samples_per_sec_min": None,
            "train_throughput_samples_per_sec_max": None,
            "train_throughput_epochs_seen": 0,
            "events": cycle_events,
            "idle_meta_payload": idle_meta_payload,
            "idle_meta_ok": bool(idle_meta_ok),
            "cleanup_payload": cleanup_payload,
            "summary_json": cycle_summary_json,
        }
        with open(cycle_summary_json, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        state["cycles_completed"] = int(state.get("cycles_completed", 0)) + 1
        state["updated_at_local"] = _now_local()
        _update_runtime_state(
            args=args,
            state=state,
            cycle_idx=int(cycle_idx),
            date_tag=str(date_tag),
            phase="idle",
            current_target="",
            note="no_candidates",
            persist=True,
        )
        return CycleResult(
            cycle=cycle_idx,
            date_tag=date_tag,
            pass_flag=True,
            core_pass=True,
            meta_pass=bool(idle_meta_ok) if bool(idle_meta_payload.get("enabled", False)) else None,
            trained_ids=[],
            failed_ids=[],
            summary_json=cycle_summary_json,
        )

    fetch_rows: List[Dict[str, Any]] = []
    for c in candidates:
        fetch_rows.append(
            {
                "target": c["runtime_target"],
                "pdb_id": c.get("pdb_id", ""),
                "uniprot_id": c.get("uniprot_id", ""),
                "pdb_url": c.get("pdb_url", ""),
                "afdb_url": c.get("afdb_url", ""),
                "notes": c.get("notes", ""),
            }
        )
    _update_runtime_state(
        args=args,
        state=state,
        cycle_idx=int(cycle_idx),
        date_tag=str(date_tag),
        phase="fetch",
        current_target="",
        note=f"targets={len(fetch_rows)}",
        persist=True,
    )
    cycle_fetch_sources_csv = f"{cycle_prefix}_sources.csv"
    pd.DataFrame(fetch_rows).to_csv(cycle_fetch_sources_csv, index=False)
    fetch_targets = ",".join([str(c["runtime_target"]) for c in candidates])
    cycle_fetch_manifest = f"{cycle_prefix}_fetch_manifest.csv"
    cycle_fetch_summary = f"{cycle_prefix}_fetch_summary.json"
    fetch_payload = fetch_public_structure_set(
        sources_csv=cycle_fetch_sources_csv,
        targets_spec=fetch_targets,
        out_dir=os.path.join(str(args.public_out_dir), date_tag),
        out_manifest_csv=cycle_fetch_manifest,
        out_summary_json=cycle_fetch_summary,
        download_pdb=True,
        download_afdb=True,
        timeout_sec=float(args.timeout_sec),
        afdb_model_versions=str(args.afdb_model_versions),
        overwrite=False,
        dry_run=bool(args.dry_run),
        strict=False,
        write_template_if_missing=False,
    )
    cycle_events.append({"name": "fetch_public_structure_set", "payload": fetch_payload.get("summary", {})})
    fetch_df = _read_csv_if_exists(cycle_fetch_manifest)

    target_to_protein_id = {str(c["runtime_target"]): str(c["protein_id"]) for c in candidates}
    protein_by_id = {str(c["protein_id"]): c for c in candidates}
    large_cycle_active = bool(args.large_loop_enabled) and int(args.include_large_every_cycles) > 0 and (
        int(cycle_idx) % int(args.include_large_every_cycles) == 0
    )
    trained_ids: List[str] = []
    failed_ids: List[str] = []
    deferred_ids: List[str] = []
    oversize_skip_ids: List[str] = []
    oversize_hard_cap_ids: List[str] = []
    failure_detail_by_pid: Dict[str, Dict[str, Any]] = {}
    large_mode_attempted_ids: List[str] = []
    large_mode_generated_ids: List[str] = []
    large_mode_failed_ids: List[str] = []
    size_mode_by_id: Dict[str, str] = {}
    generated_targets: List[str] = []
    distill_targets: List[str] = []
    base_native_dir = str(args.native_dir)
    base_h5_dir = os.path.join(str(args.h5_out_dir), date_tag)
    os.makedirs(base_native_dir, exist_ok=True)
    os.makedirs(base_h5_dir, exist_ok=True)
    env_perturb_grids = _resolve_env_perturb_grids(args)

    for runtime_target, protein_id in target_to_protein_id.items():
        cand = dict(protein_by_id.get(protein_id, {}))
        _update_runtime_state(
            args=args,
            state=state,
            cycle_idx=int(cycle_idx),
            date_tag=str(date_tag),
            phase="prepare_target",
            current_target=str(runtime_target),
            note=str(protein_id),
            persist=True,
        )
        rec = state.setdefault("proteins", {}).setdefault(protein_id, {})
        rec["runtime_target"] = str(runtime_target)
        rec["source_target"] = str(cand.get("target", ""))
        rec["pdb_id"] = str(cand.get("pdb_id", ""))
        rec["uniprot_id"] = str(cand.get("uniprot_id", ""))
        rec["priority"] = float(cand.get("priority", 0.0))
        rec["updated_at_local"] = _now_local()

        structure_path = _select_best_structure_path(fetch_df, runtime_target)
        if not structure_path:
            failed_ids.append(protein_id)
            cycle_events.append({"name": "candidate_failed", "target": runtime_target, "protein_id": protein_id, "reason": "no_structure_path"})
            failure_detail_by_pid[protein_id] = {
                "event": "candidate_failed",
                "reason": "no_structure_path",
                "target": str(runtime_target),
                "size_mode": "core",
            }
            continue

        ca_n = int(_read_ca_count(structure_path))
        rec["ca_residues"] = int(ca_n)
        rec["ca_residues_hint"] = int(ca_n)
        if ca_n < int(args.min_ca_residues):
            failed_ids.append(protein_id)
            cycle_events.append({"name": "candidate_failed", "target": runtime_target, "protein_id": protein_id, "reason": f"low_ca_count:{ca_n}"})
            failure_detail_by_pid[protein_id] = {
                "event": "candidate_failed",
                "reason": f"low_ca_count:{ca_n}",
                "target": str(runtime_target),
                "size_mode": "core",
            }
            continue

        env_profile = _pick_env_perturb_profile(
            args=args,
            cycle_idx=int(cycle_idx),
            protein_id=str(protein_id),
            runtime_target=str(runtime_target),
            grids=env_perturb_grids,
        )
        rec["last_env_profile"] = dict(env_profile)
        rec["last_env_profile_cycle"] = int(cycle_idx)

        size_mode = "core"
        datagen_samples = int(args.samples_per_target)
        datagen_timeout_sec = float(args.datagen_timeout_sec)
        openmm_steps = int(args.openmm_steps)
        if int(args.max_ca_residues) > 0 and ca_n > int(args.max_ca_residues):
            large_cap = int(args.large_loop_max_ca_residues)
            within_large_cap = (large_cap <= 0) or (ca_n <= large_cap)
            if not bool(args.large_loop_enabled):
                failed_ids.append(protein_id)
                oversize_skip_ids.append(protein_id)
                fail_reason = f"high_ca_count:{ca_n}>max:{int(args.max_ca_residues)};large_loop_disabled"
                cycle_events.append(
                    {
                        "name": "candidate_failed",
                        "target": runtime_target,
                        "protein_id": protein_id,
                        "reason": fail_reason,
                    }
                )
                failure_detail_by_pid[protein_id] = {
                    "event": "candidate_failed",
                    "reason": fail_reason,
                    "target": str(runtime_target),
                    "size_mode": "core",
                }
                continue
            if not bool(within_large_cap):
                failed_ids.append(protein_id)
                oversize_skip_ids.append(protein_id)
                oversize_hard_cap_ids.append(protein_id)
                fail_reason = f"high_ca_count_hard_cap:{ca_n}>large_cap:{int(large_cap)}"
                cycle_events.append(
                    {
                        "name": "candidate_failed",
                        "target": runtime_target,
                        "protein_id": protein_id,
                        "reason": fail_reason,
                    }
                )
                failure_detail_by_pid[protein_id] = {
                    "event": "candidate_failed",
                    "reason": fail_reason,
                    "target": str(runtime_target),
                    "size_mode": "core",
                }
                continue
            if not bool(large_cycle_active):
                deferred_ids.append(protein_id)
                size_mode_by_id[str(protein_id)] = "deferred_large"
                rec["status"] = "deferred_large_cycle"
                rec["size_mode_last"] = "deferred_large"
                rec["last_deferred_cycle"] = int(cycle_idx)
                rec["last_deferred_date_tag"] = str(date_tag)
                rec["last_cycle"] = date_tag
                rec["updated_at_local"] = _now_local()
                cycle_events.append(
                    {
                        "name": "candidate_deferred_large_cycle",
                        "target": runtime_target,
                        "protein_id": protein_id,
                        "ca_residues": int(ca_n),
                        "max_ca_residues": int(args.max_ca_residues),
                        "large_loop_max_ca_residues": int(large_cap),
                        "include_large_every_cycles": int(args.include_large_every_cycles),
                    }
                )
                continue
            size_mode = "large"
            datagen_samples = int(max(1, int(args.large_loop_samples_per_target)))
            datagen_timeout_sec = float(max(float(args.datagen_timeout_sec), float(args.large_loop_datagen_timeout_sec)))
            if int(args.large_loop_openmm_steps) > 0:
                openmm_steps = int(args.large_loop_openmm_steps)
            large_mode_attempted_ids.append(protein_id)
            cycle_events.append(
                {
                    "name": "candidate_large_mode",
                    "target": runtime_target,
                    "protein_id": protein_id,
                    "ca_residues": int(ca_n),
                    "samples_per_target": int(datagen_samples),
                    "datagen_timeout_sec": float(datagen_timeout_sec),
                    "openmm_steps": int(openmm_steps),
                    "env_profile": dict(env_profile),
                }
            )
        size_mode_by_id[str(protein_id)] = str(size_mode)

        _register_dynamic_target(runtime_target, ca_n)
        native_slug = _slug(runtime_target)
        native_path = os.path.join(base_native_dir, f"{native_slug}.pdb")
        if (not bool(args.dry_run)) and (os.path.abspath(structure_path) != os.path.abspath(native_path)):
            shutil.copyfile(structure_path, native_path)

        md_ingest = _ingest_md_artifact(
            md_df=md_df,
            candidate=cand,
            out_dir=os.path.join(str(args.md_cache_dir), date_tag),
            timeout_sec=float(args.timeout_sec),
            dry_run=bool(args.dry_run),
        )

        openmm_status = {"ok": False, "skipped": True}
        if bool(args.generate_openmm_reference):
            openmm_status = _run_openmm_reference(
                target=runtime_target,
                date_tag=date_tag,
                out_dir=os.path.join(str(args.openmm_out_dir), date_tag),
                steps=int(openmm_steps),
                save_stride=int(args.openmm_save_stride),
                strict=bool(args.strict_openmm),
            )

        if not bool(args.dry_run):
            try:
                _update_runtime_state(
                    args=args,
                    state=state,
                    cycle_idx=int(cycle_idx),
                    date_tag=str(date_tag),
                    phase="datagen",
                    current_target=str(runtime_target),
                    note=(
                        f"ca={ca_n};temp={float(env_profile.get('temp', 300.0)):.1f};"
                        f"ionic={float(env_profile.get('ionic_strength', 0.15)):.2f};"
                        f"ptm={int(round(float(env_profile.get('ptm_count', 0.0))))}"
                    ),
                    persist=True,
                )
                ok, datagen_err = _run_datagen_with_timeout(
                    target=str(runtime_target),
                    total_samples=int(datagen_samples),
                    noise=float(args.noise),
                    output_dir=str(base_h5_dir),
                    train_ratio=float(args.train_ratio),
                    val_ratio=float(args.val_ratio),
                    residual_mode=bool(args.residual_mode),
                    reference_cutoff=float(args.reference_cutoff),
                    reference_max_neighbors=int(args.reference_max_neighbors),
                    reference_force_cap=float(args.reference_force_cap),
                    force_backend=str(args.force_backend),
                    sim_params=dict(env_profile),
                    device=str(args.device),
                    device_id=int(args.device_id),
                    require_gpu=bool(args.require_gpu),
                    ca_residues=int(ca_n),
                    log_path=str(cycle_datagen_log),
                    timeout_sec=float(datagen_timeout_sec),
                )
                if (not bool(ok)) and str(datagen_err).strip():
                    cycle_events.append(
                        {
                            "name": "candidate_datagen_error",
                            "target": runtime_target,
                            "protein_id": protein_id,
                            "error": str(datagen_err),
                            "size_mode": str(size_mode),
                            "env_profile": dict(env_profile),
                        }
                    )
                    failure_detail_by_pid[protein_id] = {
                        "event": "candidate_datagen_error",
                        "reason": str(datagen_err),
                        "target": str(runtime_target),
                        "size_mode": str(size_mode),
                        "env_profile": dict(env_profile),
                    }
            except Exception as exc:
                ok = False
                cycle_events.append({"name": "candidate_exception", "target": runtime_target, "protein_id": protein_id, "error": str(exc)})
                failure_detail_by_pid[protein_id] = {
                    "event": "candidate_exception",
                    "reason": str(exc),
                    "target": str(runtime_target),
                    "size_mode": str(size_mode),
                    "env_profile": dict(env_profile),
                }
        else:
            ok = True

        if ok:
            generated_targets.append(runtime_target)
            distill_targets.append(runtime_target)
            trained_ids.append(protein_id)
            if str(size_mode) == "large":
                large_mode_generated_ids.append(protein_id)
            cycle_events.append(
                {
                    "name": "candidate_generated",
                    "target": runtime_target,
                    "protein_id": protein_id,
                    "ca_residues": int(ca_n),
                    "size_mode": str(size_mode),
                    "env_profile": dict(env_profile),
                    "native_path": os.path.abspath(native_path),
                    "md_ingest": md_ingest,
                    "openmm_reference": openmm_status,
                }
            )
        else:
            failed_ids.append(protein_id)
            if str(size_mode) == "large":
                large_mode_failed_ids.append(protein_id)
            if protein_id not in failure_detail_by_pid:
                failure_detail_by_pid[protein_id] = {
                    "event": "candidate_failed",
                    "reason": "data_generation_failed",
                    "target": str(runtime_target),
                    "size_mode": str(size_mode),
                }
            cycle_events.append(
                {
                    "name": "candidate_failed",
                    "target": runtime_target,
                    "protein_id": protein_id,
                    "reason": "data_generation_failed",
                    "size_mode": str(size_mode),
                    "env_profile": dict(env_profile),
                    "md_ingest": md_ingest,
                    "openmm_reference": openmm_status,
                }
            )

    cycle_distill_manifest = f"{cycle_prefix}_distilled_manifest.csv"
    cycle_distill_summary = f"{cycle_prefix}_distilled_summary.json"
    live_delta_manifest = f"{cycle_prefix}_live_delta_manifest.csv"
    live_manifest = str(args.live_manifest_csv)
    train_manifest = f"{cycle_prefix}_train_manifest.csv"
    merged_info: Dict[str, Any] = {}
    training_payload: Dict[str, Any] = {}
    core_training_ok = True
    meta_training_ok = True
    meta_training_payload: Dict[str, Any] = {}
    meta_training_transient_failure = False
    meta_training_attempted = False

    if len(distill_targets) > 0 and (not bool(args.dry_run)):
        _update_runtime_state(
            args=args,
            state=state,
            cycle_idx=int(cycle_idx),
            date_tag=str(date_tag),
            phase="distill",
            current_target=",".join(distill_targets[:3]),
            note=f"targets={len(distill_targets)}",
            persist=True,
        )
        distill_payload = build_distilled_residual_dataset(
            input_glob=os.path.join(base_h5_dir, "*_airouter_*_data.h5"),
            targets=",".join(distill_targets),
            out_dir=os.path.join(str(args.distilled_out_dir), date_tag),
            out_manifest_csv=cycle_distill_manifest,
            out_summary_json=cycle_distill_summary,
            float_dtype=str(args.distill_float_dtype),
            keep_coords=bool(args.distill_keep_coords),
            max_samples_per_file=None if int(args.distill_max_samples_per_file) <= 0 else int(args.distill_max_samples_per_file),
            min_quality=None,
            skip_if_exists=False,
            repair_zero_residual=False,
            zero_residual_atol=1e-8,
            repair_device=str(args.distill_repair_device),
            repair_reference_cutoff=float(args.reference_cutoff),
            repair_reference_max_neighbors=int(args.reference_max_neighbors),
            repair_reference_force_cap=float(args.reference_force_cap),
        )
        cycle_events.append({"name": "build_distilled_residual_dataset", "payload": distill_payload.get("summary", {})})

        merged_info = _merge_manifests(
            base_csv=live_manifest if os.path.exists(live_manifest) else "",
            delta_csv=cycle_distill_manifest,
            out_csv=live_delta_manifest,
        )
        if str(args.base_manifest_csv).strip() and os.path.exists(str(args.base_manifest_csv)):
            merged_info = _merge_manifests(
                base_csv=str(args.base_manifest_csv),
                delta_csv=live_delta_manifest,
                out_csv=train_manifest,
            )
        else:
            shutil.copyfile(live_delta_manifest, train_manifest)
            merged_info = {
                "rows_before": int(pd.read_csv(train_manifest).shape[0]) if os.path.exists(train_manifest) else 0,
                "rows_after": int(pd.read_csv(train_manifest).shape[0]) if os.path.exists(train_manifest) else 0,
                "base_rows": 0,
                "delta_rows": int(pd.read_csv(live_delta_manifest).shape[0]) if os.path.exists(live_delta_manifest) else 0,
                "out_csv": train_manifest,
            }
        os.makedirs(os.path.dirname(live_manifest) or ".", exist_ok=True)
        shutil.copyfile(live_delta_manifest, live_manifest)

        if bool(args.run_training):
            training_target_i = str(args.training_target).strip()
            if training_target_i.lower() == "auto":
                training_target_i = str(distill_targets[0]) if distill_targets else "*"
            _update_runtime_state(
                args=args,
                state=state,
                cycle_idx=int(cycle_idx),
                date_tag=str(date_tag),
                phase="training",
                current_target=str(training_target_i),
                note="core",
                persist=True,
            )
            core_training_ok, training_payload, best_ckpt = _run_training_job(
                args=args,
                cycle_prefix=cycle_prefix,
                date_tag=date_tag,
                state=state,
                distilled_manifest=train_manifest,
                training_target=str(training_target_i),
                seed_offset=int(cycle_idx),
                summary_suffix="training",
                log_path=cycle_training_log,
                job_kind="core",
            )
            if best_ckpt:
                state["latest_checkpoint"] = best_ckpt
            if not bool(core_training_ok):
                cycle_events.append({"name": "training_failed", "error": str(training_payload.get("error", "training_failed"))})

            run_meta_after_cycle = bool(args.run_meta_learning) and int(args.meta_learning_every_cycles) > 0
            if run_meta_after_cycle and (int(cycle_idx) % int(args.meta_learning_every_cycles) == 0):
                if bool(args.meta_async):
                    meta_launch = _launch_meta_async(
                        args=args,
                        state=state,
                        cycle_prefix=cycle_prefix,
                        date_tag=date_tag,
                        distilled_manifest=train_manifest,
                        seed_offset=int(cycle_idx) + 500000,
                        reason="after_core",
                    )
                    cycle_events.append({"name": "meta_learning_cycle", "payload": meta_launch})
                else:
                    meta_training_attempted = True
                    _update_runtime_state(
                        args=args,
                        state=state,
                        cycle_idx=int(cycle_idx),
                        date_tag=str(date_tag),
                        phase="training",
                        current_target=str(args.meta_learning_target),
                        note="meta_sync",
                        persist=True,
                    )
                    meta_ok, meta_payload, meta_ckpt = _run_training_job(
                        args=args,
                        cycle_prefix=cycle_prefix,
                        date_tag=date_tag,
                        state=state,
                        distilled_manifest=train_manifest,
                        training_target=str(args.meta_learning_target),
                        seed_offset=int(cycle_idx) + 500000,
                        summary_suffix="meta",
                        log_path=f"{cycle_prefix}_meta.log",
                        job_kind="meta",
                    )
                    meta_training_ok = bool(meta_ok)
                    meta_training_payload = meta_payload if isinstance(meta_payload, dict) else {}
                    meta_training_transient_failure = (not meta_training_ok) and bool(
                        _is_transient_training_error(meta_training_payload)
                    )
                    cycle_events.append(
                        {
                            "name": "meta_learning_cycle",
                            "payload": {
                                "ok": bool(meta_ok),
                                "training_target": str(args.meta_learning_target),
                                "training_payload": meta_payload,
                            },
                        }
                    )
                    if not meta_training_ok:
                        cycle_events.append(
                            {
                                "name": "meta_learning_non_blocking_failure",
                                "payload": {
                                    "ok": False,
                                    "transient_error": bool(meta_training_transient_failure),
                                    "error": str(meta_training_payload.get("error", "meta_training_failed")),
                                    "action": "continue_core_result_and_retry_meta_next_cycle",
                                },
                            }
                        )
                    if meta_ckpt:
                        state["latest_checkpoint"] = str(meta_ckpt)

    transient_training_failure = False
    if not core_training_ok:
        transient_training_failure = _is_transient_training_error(training_payload)
        if transient_training_failure:
            cycle_events.append(
                {
                    "name": "training_transient_failure",
                    "error": str(training_payload.get("error", "training_failed")),
                    "action": "retry_next_cycle_without_blacklist",
                }
            )
            trained_ids = []
        else:
            tr_reason = str(training_payload.get("error", "training_failed"))
            for pid in trained_ids:
                failure_detail_by_pid[str(pid)] = {
                    "event": "training_failed",
                    "reason": tr_reason,
                    "target": str(state.get("proteins", {}).get(str(pid), {}).get("runtime_target", "")),
                    "size_mode": str(size_mode_by_id.get(str(pid), "core")),
                }
            failed_ids.extend([pid for pid in trained_ids if pid not in failed_ids])
            trained_ids = []

    # state update
    fail_counts = state.get("fail_counts", {}) if isinstance(state.get("fail_counts"), dict) else {}
    requeue_tracker = state.get("requeue_tracker", {}) if isinstance(state.get("requeue_tracker"), dict) else {}
    oversize_skip_set = set(str(x) for x in oversize_skip_ids)
    for pid in failed_ids:
        if pid in oversize_skip_set:
            fail_counts[pid] = max(int(fail_counts.get(pid, 0)), int(args.max_failures_per_protein))
        else:
            fail_counts[pid] = int(fail_counts.get(pid, 0)) + 1
        rec = state.setdefault("proteins", {}).setdefault(pid, {})
        rec["status"] = "skipped_oversize" if pid in oversize_skip_set else "failed"
        rec["size_mode_last"] = str(size_mode_by_id.get(pid, "core"))
        fd = failure_detail_by_pid.get(pid, {}) if isinstance(failure_detail_by_pid.get(pid), dict) else {}
        fail_event = str(fd.get("event", "")).strip() or "candidate_failed"
        fail_reason = str(fd.get("reason", "")).strip() or str(rec.get("status", "failed"))
        fail_category = _classify_failure_category(reason=fail_reason, event=fail_event)
        rec["last_failure_event"] = fail_event
        rec["last_failure_reason"] = fail_reason
        rec["last_failure_category"] = fail_category
        rec["last_failure_cycle"] = int(cycle_idx)
        rec["last_failure_date_tag"] = str(date_tag)
        rec["last_cycle"] = date_tag
        rec["updated_at_local"] = _now_local()
        if isinstance(requeue_tracker.get(pid), dict):
            requeue_tracker[pid]["last_failure_event"] = fail_event
            requeue_tracker[pid]["last_failure_reason"] = fail_reason
            requeue_tracker[pid]["last_failure_category"] = fail_category
            requeue_tracker[pid]["updated_at_local"] = _now_local()
    deferred_set = set(str(x) for x in deferred_ids)
    for pid in deferred_ids:
        fail_counts.pop(pid, None)
        rec = state.setdefault("proteins", {}).setdefault(pid, {})
        rec["status"] = "deferred_large_cycle"
        rec["size_mode_last"] = str(size_mode_by_id.get(pid, "deferred_large"))
        rec["last_deferred_cycle"] = int(cycle_idx)
        rec["last_deferred_date_tag"] = str(date_tag)
        rec["last_cycle"] = date_tag
        rec["updated_at_local"] = _now_local()
        if isinstance(requeue_tracker.get(pid), dict):
            requeue_tracker[pid]["last_deferred_cycle"] = int(cycle_idx)
            requeue_tracker[pid]["last_deferred_date_tag"] = str(date_tag)
            requeue_tracker[pid]["updated_at_local"] = _now_local()
    for pid in trained_ids:
        fail_counts.pop(pid, None)
        rec = state.setdefault("proteins", {}).setdefault(pid, {})
        rec["status"] = "trained"
        rec["size_mode_last"] = str(size_mode_by_id.get(pid, "core"))
        rec["last_cycle"] = date_tag
        rec["trained_at_local"] = _now_local()
        rec["updated_at_local"] = _now_local()
        rec.pop("last_failure_event", None)
        rec.pop("last_failure_reason", None)
        rec.pop("last_failure_category", None)
        rec.pop("last_failure_cycle", None)
        rec.pop("last_failure_date_tag", None)
        requeue_tracker.pop(pid, None)
    for cand in candidates:
        pid = str(cand.get("protein_id", ""))
        rec = state.setdefault("proteins", {}).setdefault(pid, {})
        rec["runtime_target"] = str(cand.get("runtime_target", ""))
        rec["source_target"] = str(cand.get("target", ""))
        rec["pdb_id"] = str(cand.get("pdb_id", ""))
        rec["uniprot_id"] = str(cand.get("uniprot_id", ""))
        rec["priority"] = float(cand.get("priority", 0.0))
    state["fail_counts"] = fail_counts
    state["requeue_tracker"] = requeue_tracker

    trained_set = set(str(x) for x in state.get("trained_protein_ids", []))
    trained_set.update(trained_ids)
    state["trained_protein_ids"] = sorted(trained_set)
    failed_set = set(str(x) for x in state.get("failed_protein_ids", []))
    failed_set.update(failed_ids)
    failed_set.difference_update(set(str(x) for x in trained_ids))
    failed_set.difference_update(deferred_set)
    state["failed_protein_ids"] = sorted(failed_set)
    state["cycles_completed"] = int(state.get("cycles_completed", 0)) + 1

    cleanup_payload = {"enabled": False}
    if bool(args.cleanup_enabled):
        _update_runtime_state(
            args=args,
            state=state,
            cycle_idx=int(cycle_idx),
            date_tag=str(date_tag),
            phase="cleanup",
            current_target="",
            note="cleanup_artifacts",
            persist=True,
        )
        removed_dirs: List[str] = []
        if bool(args.cleanup_remove_h5_after_cycle):
            if _safe_rmtree(base_h5_dir):
                removed_dirs.append(os.path.abspath(base_h5_dir))
        if bool(args.cleanup_remove_public_after_cycle):
            pub_dir = os.path.join(str(args.public_out_dir), date_tag)
            if _safe_rmtree(pub_dir):
                removed_dirs.append(os.path.abspath(pub_dir))
        if bool(args.cleanup_remove_openmm_after_cycle):
            openmm_dir = os.path.join(str(args.openmm_out_dir), date_tag)
            if _safe_rmtree(openmm_dir):
                removed_dirs.append(os.path.abspath(openmm_dir))
        if bool(args.cleanup_remove_md_cache_after_cycle):
            md_cache_dir = os.path.join(str(args.md_cache_dir), date_tag)
            if _safe_rmtree(md_cache_dir):
                removed_dirs.append(os.path.abspath(md_cache_dir))
        old_cleanup = _cleanup_old_cycle_artifacts(
            out_prefix=str(args.out_prefix),
            date_tag_prefix=str(args.date_tag_prefix),
            keep_recent_cycles=int(args.cleanup_keep_recent_cycles),
            dry_run=bool(args.dry_run),
            compress_to_archive=bool(args.cleanup_compress_runs_artifacts),
            archive_dir=str(args.cleanup_archive_dir),
            delete_after_archive=bool(args.cleanup_delete_after_archive),
        )
        cleanup_payload = {
            "enabled": True,
            "removed_dirs": removed_dirs,
            "old_cycle_cleanup": old_cleanup,
        }
        cycle_events.append({"name": "cleanup_cycle_artifacts", "payload": cleanup_payload})

    rust_native_probe_payload = _run_rust_native_probe(
        args=args,
        cycle_prefix=str(cycle_prefix),
        cycle_idx=int(cycle_idx),
    )
    if bool(rust_native_probe_payload.get("attempted", False)):
        cycle_events.append({"name": "rust_native_probe", "payload": rust_native_probe_payload})
    if (
        bool(getattr(args, "rust_native_probe_fail_fast", False))
        and bool(rust_native_probe_payload.get("attempted", False))
        and (not bool(rust_native_probe_payload.get("ok", False)))
    ):
        core_training_ok = False
        cycle_events.append(
            {
                "name": "rust_native_probe_fail_fast",
                "payload": {
                    "ok": False,
                    "reason": str(rust_native_probe_payload.get("error", "rust_native_probe_failed")),
                },
            }
        )

    passed = bool(core_training_ok) and (
        (len(trained_ids) > 0)
        or (len(candidates) == 0)
        or (len(failed_ids) == 0 and len(deferred_ids) > 0)
    )
    meta_pass_value: Optional[bool] = bool(meta_training_ok) if bool(meta_training_attempted) else None
    large_subloop = {
        "enabled": bool(args.large_loop_enabled),
        "large_cycle_active": bool(large_cycle_active),
        "attempted_count": int(len(large_mode_attempted_ids)),
        "generated_count": int(len(large_mode_generated_ids)),
        "failed_count": int(len(large_mode_failed_ids)),
        "skipped_oversize_count": int(len(oversize_skip_ids)),
        "hard_cap_count": int(len(oversize_hard_cap_ids)),
        "deferred_count": int(len(deferred_ids)),
        "attempted_ids": large_mode_attempted_ids[:20],
        "generated_ids": large_mode_generated_ids[:20],
        "failed_ids": large_mode_failed_ids[:20],
        "skipped_oversize_ids": oversize_skip_ids[:20],
        "hard_cap_ids": oversize_hard_cap_ids[:20],
        "deferred_ids": deferred_ids[:20],
    }
    payload = {
        "generated_at_local": _now_local(),
        "date_tag": date_tag,
        "cycle": int(cycle_idx),
        "pass": bool(passed),
        "core_pass": bool(core_training_ok),
        "meta_pass": meta_pass_value,
        "dry_run": bool(args.dry_run),
        "candidates_selected": int(len(candidates)),
        "trained_ids": trained_ids,
        "failed_ids": failed_ids,
        "events": cycle_events,
        "artifacts": {
            "cycle_fetch_sources_csv": cycle_fetch_sources_csv,
            "cycle_fetch_manifest_csv": cycle_fetch_manifest,
            "cycle_fetch_summary_json": cycle_fetch_summary,
            "cycle_datagen_log": cycle_datagen_log,
            "cycle_distill_manifest_csv": cycle_distill_manifest,
            "cycle_distill_summary_json": cycle_distill_summary,
            "cycle_training_log": cycle_training_log,
            "live_manifest_csv": live_manifest,
            "cycle_train_manifest_csv": train_manifest,
        },
        "manifest_merge": merged_info,
        "training_payload": training_payload,
        "core_training_ok": bool(core_training_ok),
        "meta_training_ok": bool(meta_training_ok),
        "meta_training_payload": meta_training_payload,
        "meta_training_transient_failure": bool(meta_training_transient_failure),
        "training_transient_failure": bool(transient_training_failure),
        "large_subloop": large_subloop,
        "failure_backlog_summary": state.get("failure_backlog_summary", {}),
        "cleanup_payload": cleanup_payload,
        "rust_native_probe": rust_native_probe_payload,
        "summary_json": cycle_summary_json,
    }
    throughput_stats = _extract_training_throughput_stats(cycle_training_log)
    payload["source_rows"] = int(sources_df.shape[0]) if not sources_df.empty else 0
    payload["md_source_rows"] = int(md_df.shape[0]) if not md_df.empty else 0
    payload["afdb_sync_elapsed_sec"] = float(_safe_float(auto_sync_payload.get("elapsed_sec", 0.0), 0.0))
    payload["train_throughput_samples_per_sec_last"] = throughput_stats.get("last", None)
    payload["train_throughput_samples_per_sec_avg"] = throughput_stats.get("avg", None)
    payload["train_throughput_samples_per_sec_min"] = throughput_stats.get("min", None)
    payload["train_throughput_samples_per_sec_max"] = throughput_stats.get("max", None)
    payload["train_throughput_epochs_seen"] = int(_safe_float(throughput_stats.get("count", 0), 0))
    with open(cycle_summary_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    _update_runtime_state(
        args=args,
        state=state,
        cycle_idx=int(cycle_idx),
        date_tag=str(date_tag),
        phase="idle",
        current_target="",
        note="cycle_complete",
        persist=True,
    )
    return CycleResult(
        cycle=cycle_idx,
        date_tag=date_tag,
        pass_flag=bool(passed),
        core_pass=bool(core_training_ok),
        meta_pass=meta_pass_value,
        trained_ids=trained_ids,
        failed_ids=failed_ids,
        summary_json=cycle_summary_json,
    )


def build_parser() -> argparse.ArgumentParser:
    stamp = dt.date.today().isoformat()
    p = argparse.ArgumentParser(
        description=(
            "Unlimited live-learning loop for unseen proteins: fetch AFDB/PDB sources, "
            "skip already trained proteins via state file, generate distilled data, and retrain continuously."
        )
    )
    p.add_argument("--sources-csv", type=str, default="config/structure_sources_live_unseen_template.csv")
    p.add_argument("--sources-url", type=str, default="")
    p.add_argument("--md-sources-csv", type=str, default="config/high_precision_md_sources_live_template.csv")
    p.add_argument("--md-sources-url", type=str, default="")
    p.add_argument("--auto-sync-afdb-candidates", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--afdb-uniprot-query", type=str, default=DEFAULT_AFDB_UNIPROT_QUERY)
    p.add_argument("--afdb-query-size", type=int, default=500)
    p.add_argument(
        "--afdb-query-autogrow",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Increase AFDB UniProt query size automatically after consecutive no-add cycles.",
    )
    p.add_argument(
        "--afdb-query-autogrow-max-size",
        type=int,
        default=4000,
        help="Upper bound for AFDB query size when auto-grow is enabled.",
    )
    p.add_argument("--afdb-min-global-metric", type=float, default=85.0)
    p.add_argument("--afdb-add-per-cycle", type=int, default=4)
    p.add_argument(
        "--afdb-pages-per-cycle",
        type=int,
        default=3,
        help="UniProt cursor pages to scan per cycle (increases unseen candidate discovery breadth).",
    )
    p.add_argument(
        "--afdb-reset-cursor-on-empty",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Reset UniProt cursor to head when current cursor yields empty page.",
    )
    p.add_argument(
        "--afdb-max-metric-lookups-per-cycle",
        type=int,
        default=24,
        help="Cap AFDB global-metric online lookups per cycle to avoid long sync stalls.",
    )
    p.add_argument("--afdb-score-cache-json", type=str, default="runs/live_unseen_afdb_score_cache.json")
    p.add_argument(
        "--md-catalog-urls",
        type=str,
        default="",
        help="Comma-separated CSV URLs/paths containing high-precision MD catalog rows.",
    )
    p.add_argument(
        "--md-catalog-urls-file",
        type=str,
        default="config/high_precision_md_catalog_urls_live.txt",
        help="Text file with one MD catalog CSV URL/path per line.",
    )
    p.add_argument("--auto-discover-local-md-catalogs", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument(
        "--local-md-catalog-globs",
        type=str,
        default="runs/real_md_source_manifest_openmm_2bead_*.csv,runs/real_md_source_manifest_openmm_*.csv",
        help="Comma-separated glob patterns for auto-discovering local MD catalog manifests.",
    )
    p.add_argument("--local-md-catalog-max-per-glob", type=int, default=2)
    p.add_argument("--state-json", type=str, default="runs/live_unseen_learning_state.json")
    p.add_argument("--history-jsonl", type=str, default="runs/live_unseen_learning_history.jsonl")
    p.add_argument("--status-json", type=str, default="runs/live_unseen_learning_status.json")
    p.add_argument(
        "--single-instance",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Disallow multiple concurrent loop processes for the same state file.",
    )
    p.add_argument(
        "--lock-file",
        type=str,
        default="",
        help="Optional lock file path. Default: <state-json>.lock",
    )
    p.add_argument("--out-prefix", type=str, default=f"runs/live_unseen_learning_{stamp}")
    p.add_argument("--date-tag-prefix", type=str, default=f"{stamp}_live_unseen")
    p.add_argument("--new-proteins-per-cycle", type=int, default=2)
    p.add_argument("--max-failures-per-protein", type=int, default=3)
    p.add_argument("--failure-requeue-enabled", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument(
        "--failure-requeue-categories",
        type=str,
        default="datagen_failure,datagen_timeout,training_transient,missing_structure,exception,oversize_wait_large_cycle,oversize",
        help="Comma-separated failure categories eligible for bounded requeue override after max-failures threshold.",
    )
    p.add_argument("--failure-requeue-max-retries", type=int, default=2)
    p.add_argument("--failure-requeue-cooldown-cycles", type=int, default=3)
    p.add_argument("--failure-adaptive-requeue-enabled", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument(
        "--failure-adaptive-hot-categories",
        type=str,
        default="datagen_failure,datagen_timeout,training_transient,exception,training_failure,missing_structure",
        help="Failure categories considered for adaptive hotspot-based requeue policy.",
    )
    p.add_argument(
        "--failure-adaptive-transient-categories",
        type=str,
        default="datagen_failure,datagen_timeout,training_transient,exception",
        help="Hotspot categories treated as transient (extra retries + reduced cooldown).",
    )
    p.add_argument("--failure-adaptive-min-count", type=int, default=2)
    p.add_argument("--failure-adaptive-extra-retries", type=int, default=1)
    p.add_argument("--failure-adaptive-cooldown-reduction", type=int, default=1)
    p.add_argument("--failure-breakdown-enabled", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--failure-breakdown-json", type=str, default="runs/live_unseen_failure_breakdown_rolling.json")
    p.add_argument("--failure-breakdown-csv", type=str, default="runs/live_unseen_failure_breakdown_rolling.csv")
    p.add_argument("--failure-breakdown-max-scan-summaries", type=int, default=500)
    p.add_argument("--failure-breakdown-refresh-cycles", type=int, default=1)
    p.add_argument(
        "--candidate-order-policy",
        type=str,
        default="size_curriculum",
        choices=["priority", "size_curriculum"],
        help="Candidate ordering policy before per-cycle sampling.",
    )
    p.add_argument("--small-ca-threshold", type=int, default=220)
    p.add_argument("--medium-ca-threshold", type=int, default=600)
    p.add_argument(
        "--include-large-every-cycles",
        type=int,
        default=1,
        help="When size_curriculum is enabled, include large-hint candidates every N cycles.",
    )
    p.add_argument(
        "--include-large-probe-on-non-large-cycle",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Optionally keep a single large probe candidate even when not in a dedicated large cycle.",
    )
    p.add_argument(
        "--oversize-recovery-if-idle",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="When no normal candidates are selected, inject oversize requeue candidates to avoid stagnation.",
    )
    p.add_argument(
        "--oversize-recovery-topk",
        type=int,
        default=1,
        help="Max oversize recovery candidates to inject per cycle when idle.",
    )
    p.add_argument("--sleep-sec", type=float, default=30.0)
    p.add_argument("--max-cycles", type=int, default=0, help="0 means infinite loop")
    p.add_argument("--stop-file", type=str, default="runs/STOP_LIVE_UNSEEN_LEARNING")

    p.add_argument("--public-out-dir", type=str, default="data/public_structures/live_unseen")
    p.add_argument("--native-dir", type=str, default="data/native")
    p.add_argument("--h5-out-dir", type=str, default="data/live_unseen_h5")
    p.add_argument("--distilled-out-dir", type=str, default="data/live_unseen_distilled")
    p.add_argument("--md-cache-dir", type=str, default="data/live_unseen_md_cache")
    p.add_argument("--openmm-out-dir", type=str, default="runs/live_unseen_openmm")
    p.add_argument("--live-manifest-csv", type=str, default="runs/distilled_residual_manifest_live_unseen.csv")
    p.add_argument("--base-manifest-csv", type=str, default="runs/distilled_residual_manifest_bigdata_afdb_weighted_2026-02-15.csv")

    p.add_argument("--samples-per-target", type=int, default=1200)
    p.add_argument("--noise", type=float, default=0.10)
    p.add_argument("--train-ratio", type=float, default=0.8)
    p.add_argument("--val-ratio", type=float, default=0.1)
    p.add_argument("--min-ca-residues", type=int, default=8)
    p.add_argument(
        "--max-ca-residues",
        type=int,
        default=0,
        help="Skip oversized proteins when CA residue count exceeds this threshold (0 disables).",
    )
    p.add_argument(
        "--large-loop-enabled",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable dedicated large-protein subloop on configured cycles.",
    )
    p.add_argument(
        "--large-loop-max-ca-residues",
        type=int,
        default=0,
        help="Upper CA limit accepted by large subloop when max-ca-residues is exceeded (0 disables cap).",
    )
    p.add_argument(
        "--large-loop-samples-per-target",
        type=int,
        default=20,
        help="Reduced per-target samples for large subloop candidates.",
    )
    p.add_argument(
        "--large-loop-datagen-timeout-sec",
        type=float,
        default=1800.0,
        help="Datagen timeout for large subloop candidates.",
    )
    p.add_argument(
        "--large-loop-openmm-steps",
        type=int,
        default=0,
        help="OpenMM reference steps override for large subloop (0 keeps openmm-steps).",
    )
    p.add_argument("--residual-mode", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--force-backend", type=str, default="auto", choices=["auto", "pytorch"])
    p.add_argument("--reference-cutoff", type=float, default=14.0)
    p.add_argument("--reference-max-neighbors", type=int, default=160)
    p.add_argument("--reference-force-cap", type=float, default=100.0)
    p.add_argument("--distill-float-dtype", type=str, default="float16", choices=["float16", "float32"])
    p.add_argument("--distill-keep-coords", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--distill-max-samples-per-file", type=int, default=0)
    p.add_argument(
        "--datagen-timeout-sec",
        type=float,
        default=900.0,
        help="Timeout for per-target data generation; target is marked failed on timeout.",
    )
    p.add_argument(
        "--env-perturb-enabled",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Inject per-cycle runtime environment perturbation profile into generated data.",
    )
    p.add_argument("--env-perturb-temp-grid", type=str, default="280,300,330,360,420")
    p.add_argument("--env-perturb-salt-conc-grid", type=str, default="0.05,0.10,0.20,0.30")
    p.add_argument("--env-perturb-ph-grid", type=str, default="6.5,7.0,7.4,8.0")
    p.add_argument("--env-perturb-ionic-strength-grid", type=str, default="0.05,0.15,0.30,0.50")
    p.add_argument("--env-perturb-ptm-count-grid", type=str, default="0,1,2,3")
    p.add_argument("--env-perturb-force-scale-grid", type=str, default="0.9,1.0,1.1")
    p.add_argument("--env-perturb-cooling-rate-grid", type=str, default="-1.0,0.0,1.0")
    p.add_argument("--env-perturb-hydro-strength-grid", type=str, default="0.9,1.0,1.1")
    p.add_argument("--env-perturb-k-angle-grid", type=str, default="20.0,25.0,30.0")
    p.add_argument("--env-perturb-theta0-grid", type=str, default="100.0,109.5,120.0")
    p.add_argument("--env-perturb-k-dihedral-grid", type=str, default="0.5,1.0,2.0")
    p.add_argument("--env-perturb-phi0-alpha-grid", type=str, default="-70.0,-57.0,-45.0")
    p.add_argument("--env-perturb-ai-correction-active-grid", type=str, default="1.0")

    p.add_argument("--run-training", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--training-target", type=str, default="auto")
    p.add_argument("--training-schedule", type=str, default="size_ascending")
    p.add_argument("--training-max-targets", type=int, default=0)
    p.add_argument("--training-early-stop-patience", type=int, default=6)
    p.add_argument("--training-hp-search", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--checkpoint-dir", type=str, default="models/curriculum_live_unseen")
    p.add_argument("--run-meta-learning", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--run-meta-learning-when-idle", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--meta-learning-every-cycles", type=int, default=3)
    p.add_argument("--meta-learning-target", type=str, default="*")
    p.add_argument(
        "--meta-async",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Run meta-learning in detached async worker so core cycle is non-blocking.",
    )
    p.add_argument(
        "--meta-async-max-runtime-sec",
        type=float,
        default=5400.0,
        help="Kill async meta worker when runtime exceeds this timeout (0 disables).",
    )
    p.add_argument(
        "--meta-async-kill-orphan",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Kill stale/orphan async meta worker if parent is gone (or worker re-parented to init).",
    )

    p.add_argument("--cleanup-enabled", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--cleanup-keep-recent-cycles", type=int, default=20)
    p.add_argument(
        "--cleanup-compress-runs-artifacts",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Archive old per-cycle run artifacts into tar.gz files before deletion.",
    )
    p.add_argument(
        "--cleanup-archive-dir",
        type=str,
        default="archives/live_unseen_runs",
        help="Directory where archived cycle tar.gz files are stored.",
    )
    p.add_argument(
        "--cleanup-delete-after-archive",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Delete original cycle files after successful archive creation.",
    )
    p.add_argument("--cleanup-remove-h5-after-cycle", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--cleanup-remove-public-after-cycle", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--cleanup-remove-openmm-after-cycle", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--cleanup-remove-md-cache-after-cycle", action=argparse.BooleanOptionalAction, default=False)

    p.add_argument("--generate-openmm-reference", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--strict-openmm", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--openmm-steps", type=int, default=3000)
    p.add_argument("--openmm-save-stride", type=int, default=200)

    p.add_argument("--afdb-model-versions", type=str, default="v6,v5,v4")
    p.add_argument("--device", type=str, default="cuda", choices=["cpu", "cuda", "mps"])
    p.add_argument("--device-id", type=int, default=0)
    p.add_argument(
        "--ai-router-runtime-mode",
        type=str,
        default="auto",
        choices=["auto", "eager", "scripted", "compiled", "onnx"],
        help="Runtime mode for AIRouter inference path.",
    )
    p.add_argument(
        "--ai-router-auto-try-onnx",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="When runtime-mode=auto, allow ONNX fallback after compile path.",
    )
    p.add_argument(
        "--ai-router-onnx-providers",
        type=str,
        default="ROCMExecutionProvider,CUDAExecutionProvider",
        help="Comma-separated ONNXRuntime providers (GPU-first).",
    )
    p.add_argument(
        "--ai-router-compile-mode",
        type=str,
        default="reduce-overhead",
        help="torch.compile mode for AIRouter compile path.",
    )
    p.add_argument(
        "--onnx-require-iobinding",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Require ONNX IOBinding for CUDA path (enforces GPU zero-copy path).",
    )
    p.add_argument(
        "--onnx-allow-cpu-copy",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Allow CPU copy fallback if ONNX iobinding path fails.",
    )
    p.add_argument(
        "--trainer-torch-compile",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable torch.compile for training model path.",
    )
    p.add_argument("--trainer-torch-compile-mode", type=str, default="reduce-overhead")
    p.add_argument(
        "--trainer-torch-compile-fullgraph",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    p.add_argument(
        "--trainer-torch-compile-dynamic",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    p.add_argument(
        "--require-gpu",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Fail-fast when CUDA device is unavailable or non-CUDA device is selected.",
    )
    p.add_argument(
        "--distill-repair-device",
        type=str,
        default="cuda",
        choices=["cpu", "cuda", "mps"],
        help="Device used by distilled residual zero-force repair pass.",
    )
    p.add_argument("--timeout-sec", type=float, default=45.0)
    p.add_argument("--seed", type=int, default=20260219)
    p.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--fail-fast", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--success-gate-enabled", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--success-gate-window", type=int, default=24)
    p.add_argument("--success-gate-warmup-cycles", type=int, default=8)
    p.add_argument("--success-gate-min-pass-rate-pct", type=float, default=35.0)
    p.add_argument("--success-gate-min-core-pass-rate-pct", type=float, default=45.0)
    p.add_argument("--success-gate-min-avg-trained-per-cycle", type=float, default=0.25)
    p.add_argument("--success-gate-max-failed-sum", type=int, default=40)
    p.add_argument("--success-gate-max-consecutive-fail", type=int, default=10)
    p.add_argument(
        "--success-gate-action",
        type=str,
        default="none",
        choices=["none", "cooldown", "stop"],
        help="Action when recent success gate fails.",
    )
    p.add_argument("--success-gate-cooldown-sec", type=float, default=120.0)
    p.add_argument("--quality-guard-enabled", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--quality-guard-window", type=int, default=12)
    p.add_argument("--quality-guard-warmup-cycles", type=int, default=8)
    p.add_argument("--quality-guard-min-metrics-rows", type=int, default=4)
    p.add_argument("--quality-guard-max-regression-pct", type=float, default=15.0)
    p.add_argument(
        "--quality-guard-action",
        type=str,
        default="cooldown",
        choices=["none", "cooldown", "stop"],
        help="Action when recent quality trend regresses beyond threshold.",
    )
    p.add_argument("--quality-guard-cooldown-sec", type=float, default=180.0)
    p.add_argument(
        "--rust-native-probe-enabled",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Run Rust-native ONNX inference PoC periodically inside loop.",
    )
    p.add_argument("--rust-native-probe-every-cycles", type=int, default=10)
    p.add_argument("--rust-native-probe-target", type=str, default="Chignolin")
    p.add_argument("--rust-native-probe-batch", type=int, default=1)
    p.add_argument("--rust-native-probe-atoms", type=int, default=0)
    p.add_argument("--rust-native-probe-topo-dim", type=int, default=64)
    p.add_argument("--rust-native-probe-sim-dim", type=int, default=19)
    p.add_argument("--rust-native-probe-timeout-sec", type=float, default=600.0)
    p.add_argument(
        "--rust-native-probe-fail-fast",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    p.add_argument("--rust-native-probe-cargo-manifest", type=str, default="rust_engine/Cargo.toml")
    p.add_argument("--rust-native-probe-onnx-path", type=str, default="")
    p.add_argument("--rust-native-probe-ai-router-checkpoint", type=str, default="")
    p.add_argument(
        "--rust-native-probe-ai-router-checkpoint-strict",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    return p


def run_loop(args: argparse.Namespace) -> Dict[str, Any]:
    device_i = str(args.device).strip().lower()
    if bool(args.require_gpu):
        if device_i != "cuda":
            raise RuntimeError(f"gpu_required_but_device_is_{device_i}")
        if not torch.cuda.is_available():
            raise RuntimeError("gpu_required_but_cuda_unavailable")
        dev_count = int(torch.cuda.device_count())
        if dev_count <= 0:
            raise RuntimeError("gpu_required_but_no_cuda_device")
        if (int(args.device_id) < 0) or (int(args.device_id) >= dev_count):
            raise RuntimeError(f"gpu_device_id_out_of_range:{int(args.device_id)}/{dev_count}")
        os.environ["FORCE_RUST_HIP"] = "1"
        os.environ["RUST_HIP_USE_GPU_NBLIST_BUILDER"] = "1"
        os.environ["RUST_HIP_NBLIST_AUTOGROW"] = "1"
        os.environ["AI_ROUTER_ONNX_ALLOW_CPU"] = "0"
        os.environ["MD_GPU_ONLY"] = "1"

    runtime_accel_profile = _apply_runtime_acceleration_profile(args)

    dev_cfg = core_config.config.setdefault("device", {})
    dev_cfg["type"] = str(args.device)
    if str(args.device).lower() == "cuda":
        dev_cfg["id"] = int(args.device_id)

    state = _load_state(str(args.state_json))
    state["runtime_acceleration_profile"] = runtime_accel_profile
    state["runtime_acceleration_profile_updated_at_local"] = _now_local()
    # Startup hygiene: clear stale async meta worker state if parent died in previous run.
    _ = _poll_meta_async_status(args=args, state=state)
    if bool(args.failure_breakdown_enabled):
        try:
            _refresh_failure_backlog_snapshot(args=args, state=state)
            _save_state(str(args.state_json), state)
        except Exception as exc:
            state["failure_backlog_summary_error"] = str(exc)
            _save_state(str(args.state_json), state)
    cycle = int(state.get("cycles_completed", 0)) + 1
    max_cycles = int(args.max_cycles)
    stop_file = str(args.stop_file)
    started = _now_local()
    while True:
        if max_cycles > 0 and cycle > max_cycles:
            break
        if stop_file and os.path.exists(stop_file):
            break

        _update_runtime_state(
            args=args,
            state=state,
            cycle_idx=int(cycle),
            date_tag=f"{args.date_tag_prefix}_{cycle:03d}",
            phase="cycle_dispatch",
            current_target="",
            note="dispatch",
            persist=True,
        )
        res = _run_cycle(args=args, cycle_idx=cycle, state=state)
        _save_state(str(args.state_json), state)
        history_row: Dict[str, Any] = {
            "timestamp_local": _now_local(),
            "cycle": int(res.cycle),
            "date_tag": res.date_tag,
            "pass": bool(res.pass_flag),
            "core_pass": bool(res.core_pass),
            "meta_pass": (None if res.meta_pass is None else bool(res.meta_pass)),
            "trained_ids_count": int(len(res.trained_ids)),
            "failed_ids_count": int(len(res.failed_ids)),
            "summary_json": res.summary_json,
        }
        gate_state: Dict[str, Any] = {"enabled": bool(args.success_gate_enabled), "pass": True, "reason": "disabled"}
        if bool(args.success_gate_enabled):
            prev_rows = _read_recent_jsonl(
                str(args.history_jsonl),
                max(1, int(args.success_gate_window) - 1),
            )
            eval_rows = prev_rows + [history_row]
            gate_state = _evaluate_success_gate(
                eval_rows,
                warmup_cycles=int(args.success_gate_warmup_cycles),
                min_pass_rate_pct=float(args.success_gate_min_pass_rate_pct),
                min_core_pass_rate_pct=float(args.success_gate_min_core_pass_rate_pct),
                min_avg_trained_per_cycle=float(args.success_gate_min_avg_trained_per_cycle),
                max_failed_sum=int(args.success_gate_max_failed_sum),
                max_consecutive_fail=int(args.success_gate_max_consecutive_fail),
            )
            gate_state["enabled"] = True
            gate_state["cycle"] = int(res.cycle)
            gate_state["date_tag"] = str(res.date_tag)
            history_row["success_gate_pass"] = bool(gate_state.get("pass", False))
            history_row["success_gate_reason"] = str(gate_state.get("reason", ""))
            history_row["success_gate_failed_checks"] = list(gate_state.get("failed_checks", []))
            state["success_gate"] = gate_state
        quality_state: Dict[str, Any] = {"enabled": bool(args.quality_guard_enabled), "pass": True, "reason": "disabled"}
        if bool(args.quality_guard_enabled):
            prev_rows_q = _read_recent_jsonl(
                str(args.history_jsonl),
                max(1, int(args.quality_guard_window) - 1),
            )
            eval_rows_q = prev_rows_q + [history_row]
            quality_state = _evaluate_quality_guard(
                eval_rows_q,
                window=int(args.quality_guard_window),
                warmup_cycles=int(args.quality_guard_warmup_cycles),
                min_metrics_rows=int(args.quality_guard_min_metrics_rows),
                max_regression_pct=float(args.quality_guard_max_regression_pct),
            )
            quality_state["enabled"] = True
            quality_state["cycle"] = int(res.cycle)
            quality_state["date_tag"] = str(res.date_tag)
            history_row["quality_guard_pass"] = bool(quality_state.get("pass", False))
            history_row["quality_guard_reason"] = str(quality_state.get("reason", ""))
            history_row["quality_guard_trend"] = str(quality_state.get("trend", "n/a"))
            history_row["quality_guard_failed_checks"] = list(quality_state.get("failed_checks", []))
            history_row["quality_guard_rmse_delta_pct"] = quality_state.get("rmse_delta_pct", None)
            history_row["quality_guard_val_loss_delta_pct"] = quality_state.get("val_loss_delta_pct", None)
            state["quality_guard"] = quality_state

        if bool(args.failure_breakdown_enabled) and (
            int(max(1, int(args.failure_breakdown_refresh_cycles))) <= 1
            or (int(res.cycle) % int(max(1, int(args.failure_breakdown_refresh_cycles))) == 0)
        ):
            try:
                breakdown_payload = _refresh_failure_backlog_snapshot(args=args, state=state)
                history_row["failure_backlog_total"] = int(breakdown_payload.get("failed_total", 0))
                history_row["failure_backlog_by_category"] = breakdown_payload.get("by_category", {})
            except Exception as exc:
                history_row["failure_backlog_error"] = str(exc)

        _save_state(str(args.state_json), state)
        _append_jsonl(str(args.history_jsonl), history_row)

        sleep_sec_next = float(args.sleep_sec)
        stop_now = False
        gate_failed = bool(args.success_gate_enabled) and (not bool(gate_state.get("pass", True)))
        if gate_failed:
            action = str(args.success_gate_action).strip().lower()
            fail_checks = gate_state.get("failed_checks", []) if isinstance(gate_state.get("failed_checks"), list) else []
            note = f"gate_fail:{';'.join(str(x) for x in fail_checks[:3])}" if fail_checks else "gate_fail"
            if action == "stop":
                _update_runtime_state(
                    args=args,
                    state=state,
                    cycle_idx=int(cycle),
                    date_tag=f"{args.date_tag_prefix}_{cycle:03d}",
                    phase="success_gate",
                    current_target="",
                    note=note,
                    persist=True,
                )
                stop_now = True
            if action == "cooldown":
                sleep_sec_next = max(float(sleep_sec_next), float(args.success_gate_cooldown_sec))
                _update_runtime_state(
                    args=args,
                    state=state,
                    cycle_idx=int(cycle),
                    date_tag=f"{args.date_tag_prefix}_{cycle:03d}",
                    phase="success_gate",
                    current_target="",
                    note=f"{note};cooldown={sleep_sec_next:.1f}",
                    persist=True,
                )
        quality_failed = bool(args.quality_guard_enabled) and (not bool(quality_state.get("pass", True)))
        if (not stop_now) and quality_failed:
            q_action = str(args.quality_guard_action).strip().lower()
            q_checks = quality_state.get("failed_checks", []) if isinstance(quality_state.get("failed_checks"), list) else []
            q_note = f"quality_fail:{';'.join(str(x) for x in q_checks[:3])}" if q_checks else "quality_fail"
            if q_action == "stop":
                _update_runtime_state(
                    args=args,
                    state=state,
                    cycle_idx=int(cycle),
                    date_tag=f"{args.date_tag_prefix}_{cycle:03d}",
                    phase="quality_guard",
                    current_target="",
                    note=q_note,
                    persist=True,
                )
                stop_now = True
            if q_action == "cooldown":
                sleep_sec_next = max(float(sleep_sec_next), float(args.quality_guard_cooldown_sec))
                _update_runtime_state(
                    args=args,
                    state=state,
                    cycle_idx=int(cycle),
                    date_tag=f"{args.date_tag_prefix}_{cycle:03d}",
                    phase="quality_guard",
                    current_target="",
                    note=f"{q_note};cooldown={sleep_sec_next:.1f}",
                    persist=True,
                )
        if stop_now:
            break
        if (not res.pass_flag) and bool(args.fail_fast):
            break
        cycle += 1
        if max_cycles > 0 and cycle > max_cycles:
            break
        if stop_file and os.path.exists(stop_file):
            break
        _update_runtime_state(
            args=args,
            state=state,
            cycle_idx=int(cycle),
            date_tag=f"{args.date_tag_prefix}_{cycle:03d}",
            phase="sleep",
            current_target="",
            note=f"sleep_sec={float(sleep_sec_next):.1f}",
            persist=True,
        )
        time.sleep(max(float(sleep_sec_next), 0.0))

    status = {
        "generated_at_local": _now_local(),
        "started_at_local": started,
        "ended_at_local": _now_local(),
        "state_json": os.path.abspath(str(args.state_json)),
        "history_jsonl": os.path.abspath(str(args.history_jsonl)),
        "cycles_completed": int(state.get("cycles_completed", 0)),
        "trained_count": int(len(state.get("trained_protein_ids", []))),
        "failed_count": int(len(state.get("failed_protein_ids", []))),
        "latest_checkpoint": str(state.get("latest_checkpoint", "")),
        "success_gate": state.get("success_gate", {}),
        "quality_guard": state.get("quality_guard", {}),
        "failure_backlog_summary": state.get("failure_backlog_summary", {}),
        "failure_requeue_policy": state.get("failure_requeue_policy", {}),
        "stop_file": str(args.stop_file),
    }
    os.makedirs(os.path.dirname(str(args.status_json)) or ".", exist_ok=True)
    with open(str(args.status_json), "w", encoding="utf-8") as f:
        json.dump(status, f, indent=2, ensure_ascii=False)
    return status


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    lock_fd = -1
    lock_meta: Dict[str, Any] = {"ok": False}
    if bool(args.single_instance):
        lock_path = str(args.lock_file).strip() or (str(args.state_json).strip() + ".lock")
        lock_fd, lock_meta = _acquire_instance_lock(lock_path)
        if lock_fd < 0:
            payload = {
                "ok": False,
                "error": "another_instance_running",
                "lock": lock_meta,
                "state_json": os.path.abspath(str(args.state_json)),
            }
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            sys.exit(3)
    status = run_loop(args)
    if lock_fd >= 0:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        except Exception:
            pass
        try:
            os.close(lock_fd)
        except Exception:
            pass
    print(json.dumps(status, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
