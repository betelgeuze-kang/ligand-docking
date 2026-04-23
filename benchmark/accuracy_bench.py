#!/usr/bin/env python3
# benchmark/accuracy_bench.py

from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import torch

from benchmark.performance_bench import benchmark_simulation
from core.config import config
from core.definitions import ResearchConstants
from run_refinement import run_target
from tools.pdb_loader import load_native_structure


def calculate_rmsd(coords1: torch.Tensor, coords2: torch.Tensor) -> float:
    """
    Calculates RMSD between two coordinate sets.
    """
    if coords1.shape != coords2.shape:
        raise ValueError(f"Coordinate shapes do not match: {coords1.shape} vs {coords2.shape}")
    diff = coords1 - coords2
    return float(torch.sqrt(diff.pow(2).sum(dim=-1).mean()).item())


def calculate_rmsd_aligned(coords1: torch.Tensor, coords2: torch.Tensor) -> float:
    """
    Kabsch-aligned RMSD (translation/rotation removed).
    """
    if coords1.shape != coords2.shape:
        raise ValueError(f"Coordinate shapes do not match: {coords1.shape} vs {coords2.shape}")
    if coords1.ndim != 2 or coords1.shape[1] != 3:
        raise ValueError(f"Coordinates must be [N,3], got {coords1.shape}")

    x = coords1 - coords1.mean(dim=0, keepdim=True)
    y = coords2 - coords2.mean(dim=0, keepdim=True)
    cov = x.transpose(0, 1) @ y
    u, _s, vh = torch.linalg.svd(cov)
    v = vh.transpose(0, 1)
    d = torch.det(u @ v.transpose(0, 1))
    if float(d.item()) < 0.0:
        u = u.clone()
        u[:, -1] *= -1.0
    r = u @ v.transpose(0, 1)
    x_aligned = x @ r
    diff = x_aligned - y
    return float(torch.sqrt(diff.pow(2).sum(dim=-1).mean()).item())


def calculate_radius_of_gyration(coords: torch.Tensor) -> float:
    """
    Calculates Radius of Gyration (Rg).
    """
    center_of_mass = coords.mean(dim=0, keepdim=True)
    distances_sq = (coords - center_of_mass).pow(2).sum(dim=-1)
    return float(torch.sqrt(distances_sq.mean()).item())


def _normalize_target_key(name: str) -> str:
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


def _normalize_representation(raw: Any) -> str:
    s = str(raw).strip().lower()
    if not s:
        return "ca"
    if s in ("ca", "ca_only", "ca_bead"):
        return "ca"
    if s in ("ca_sc_2bead", "ca_sc", "2bead", "two_bead", "ca_sc_explicit"):
        return "ca_sc_2bead"
    return "ca"


def _normalize_bead_order(raw: Any) -> str:
    s = str(raw).strip().lower()
    if s in ("interleaved_ca_sc", "ca_sc_interleaved", "interleaved"):
        return "interleaved_ca_sc"
    return "ca_then_sc"


def _extract_ca_from_2bead(
    coords: torch.Tensor,
    bead_order: str = "ca_then_sc",
    expected_ca_count: Optional[int] = None,
) -> torch.Tensor:
    if coords.ndim != 2 or coords.shape[1] != 3:
        raise ValueError(f"coordinates must be [N,3], got {coords.shape}")
    n_atoms = int(coords.shape[0])
    if n_atoms % 2 != 0:
        raise ValueError(f"2-bead projection requires even atom count, got {n_atoms}")
    n_ca = int(expected_ca_count) if expected_ca_count is not None else int(n_atoms // 2)
    if int(n_ca * 2) != n_atoms:
        raise ValueError(f"expected_ca_count mismatch: n_atoms={n_atoms}, expected_ca_count={n_ca}")
    if _normalize_bead_order(bead_order) == "interleaved_ca_sc":
        return coords[0::2]
    return coords[:n_ca]


def _expand_ca_to_explicit_2bead(simulated_ca: torch.Tensor) -> torch.Tensor:
    if simulated_ca.ndim != 2 or simulated_ca.shape[1] != 3:
        raise ValueError(f"simulated coordinates must be [N,3], got {simulated_ca.shape}")
    offset = torch.tensor([0.0, 1.5, 0.0], dtype=simulated_ca.dtype, device=simulated_ca.device).view(1, 3)
    simulated_sc = simulated_ca + offset.expand(simulated_ca.shape[0], 3)
    return torch.cat([simulated_ca, simulated_sc], dim=0)


def _reconcile_compare_coords(
    simulated_coords: torch.Tensor,
    reference_coords: torch.Tensor,
    reference_meta: Dict[str, Any],
    compare_bead: str,
) -> Tuple[torch.Tensor, torch.Tensor, str]:
    mode = str(compare_bead).strip().lower()
    if mode not in ("auto", "ca", "all"):
        raise ValueError(f"compare_bead must be one of auto|ca|all, got: {compare_bead}")
    if simulated_coords.shape == reference_coords.shape:
        return simulated_coords, reference_coords, "none"
    if mode == "all":
        return simulated_coords, reference_coords, "none"

    ref_n = int(reference_coords.shape[0])
    sim_n = int(simulated_coords.shape[0])
    ref_rep = _normalize_representation(reference_meta.get("reference_representation", ""))
    ref_order = _normalize_bead_order(reference_meta.get("reference_bead_order", ""))

    if ref_n == (2 * sim_n) and (ref_rep == "ca_sc_2bead" or mode == "ca"):
        ref_ca = _extract_ca_from_2bead(reference_coords, bead_order=ref_order, expected_ca_count=sim_n)
        return simulated_coords, ref_ca, "reference_projected_to_ca"
    if sim_n == (2 * ref_n):
        sim_ca = _extract_ca_from_2bead(simulated_coords, bead_order="ca_then_sc", expected_ca_count=ref_n)
        return sim_ca, reference_coords, "simulated_projected_to_ca"
    return simulated_coords, reference_coords, "none"


def _parse_targets(spec: str) -> List[str]:
    if str(spec).strip().lower() == "all":
        return list(ResearchConstants.CHALLENGES.keys())
    return [x.strip() for x in str(spec).split(",") if x.strip()]


def _optional_str(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    if s.lower() in ("none", "null"):
        return None
    return s


def _parse_neighbor_settings(spec: str) -> Dict[str, Any]:
    if not spec:
        return {}
    out: Dict[str, Any] = {}
    for kv in str(spec).split(","):
        kv = kv.strip()
        if not kv:
            continue
        if "=" not in kv:
            raise ValueError(f"invalid neighbor setting entry: {kv}")
        key, val = kv.split("=", 1)
        key = key.strip()
        val = val.strip()
        if "." in val:
            out[key] = float(val)
        else:
            try:
                out[key] = int(val)
            except ValueError:
                out[key] = float(val)
    return out


def _coerce_coords_tensor(arr: np.ndarray, frame: int = -1) -> torch.Tensor:
    a = np.asarray(arr)
    if a.ndim == 3:
        idx = int(frame)
        if idx < 0:
            idx = a.shape[0] - 1
        if idx >= a.shape[0]:
            raise ValueError(f"Requested frame index {idx} out of range for shape {a.shape}")
        a = a[idx]
    if a.ndim != 2:
        raise ValueError(f"Coordinate array must be [N,3] or [T,N,3], got shape {a.shape}")
    if a.shape[1] != 3 and a.shape[0] == 3:
        a = a.T
    if a.shape[1] != 3:
        raise ValueError(f"Coordinate array must have 3 columns, got shape {a.shape}")
    return torch.as_tensor(a, dtype=torch.float32, device=config.DEVICE)


def _load_coords_from_csv(path: str, frame: int = -1) -> torch.Tensor:
    df = pd.read_csv(path)
    cols = set(df.columns)
    xyz_sets = [
        ("x", "y", "z"),
        ("coord_x", "coord_y", "coord_z"),
        ("X", "Y", "Z"),
    ]
    xyz = None
    for cset in xyz_sets:
        if set(cset).issubset(cols):
            xyz = cset
            break
    if xyz is None:
        raise ValueError(f"CSV reference {path} must include xyz columns (x/y/z or coord_x/y/z)")

    use_df = df
    if "frame" in use_df.columns:
        if int(frame) < 0:
            selected = int(use_df["frame"].max())
        else:
            selected = int(frame)
        use_df = use_df[use_df["frame"] == selected]
        if use_df.empty:
            raise ValueError(f"CSV reference {path} has no rows for frame={selected}")
    arr = use_df.loc[:, list(xyz)].to_numpy(dtype=np.float32)
    return _coerce_coords_tensor(arr, frame=-1)


def _load_coords_file(path: str, key: Optional[str] = None, frame: int = -1) -> torch.Tensor:
    path_i = os.path.abspath(path)
    ext = os.path.splitext(path_i)[1].lower()
    if ext == ".npy":
        arr = np.load(path_i)
        return _coerce_coords_tensor(arr, frame=frame)
    if ext == ".npz":
        z = np.load(path_i)
        if key:
            if key not in z:
                raise KeyError(f"Key '{key}' not found in {path_i}. Available: {list(z.keys())}")
            arr = z[key]
        else:
            if len(z.files) == 0:
                raise ValueError(f"NPZ file {path_i} has no arrays.")
            arr = z[z.files[0]]
        return _coerce_coords_tensor(arr, frame=frame)
    if ext == ".csv":
        return _load_coords_from_csv(path_i, frame=frame)
    raise ValueError(f"Unsupported coordinate file extension: {ext} (path={path_i})")


def _read_external_manifest(path: str) -> Dict[str, Dict[str, Any]]:
    path_i = os.path.abspath(path)
    ext = os.path.splitext(path_i)[1].lower()
    rows: List[Dict[str, Any]] = []
    if ext == ".csv":
        rows = pd.read_csv(path_i).to_dict(orient="records")
    elif ext == ".json":
        with open(path_i, "r", encoding="utf-8") as f:
            payload = json.load(f)
        if isinstance(payload, list):
            rows = [dict(x) for x in payload]
        elif isinstance(payload, dict):
            if isinstance(payload.get("entries"), list):
                rows = [dict(x) for x in payload["entries"]]
            elif isinstance(payload.get("targets"), dict):
                for t_name, item in payload["targets"].items():
                    if isinstance(item, dict):
                        rows.append({"target": t_name, **item})
            else:
                raise ValueError("JSON manifest must include list payload, entries[], or targets{}.")
        else:
            raise ValueError("JSON manifest must be object or array.")
    else:
        raise ValueError(f"Unsupported manifest extension: {ext}. Use .csv or .json")

    out: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        target = str(row.get("target", "")).strip()
        if not target:
            continue
        key = _normalize_target_key(target)
        out[key] = row
    return out


def _resolve_manifest_entry(
    manifest: Dict[str, Dict[str, Any]],
    target: str,
) -> Optional[Dict[str, Any]]:
    return manifest.get(_normalize_target_key(target))


def _load_reference_coords(
    target: str,
    reference_source: str,
    external_manifest: Optional[Dict[str, Dict[str, Any]]] = None,
    external_key: Optional[str] = None,
    external_frame: int = -1,
) -> Tuple[torch.Tensor, Dict[str, Any]]:
    src = str(reference_source).strip().lower()
    if src == "native":
        ref_coords, _ = load_native_structure(target)
        if ref_coords is None:
            raise FileNotFoundError(f"Native structure for target '{target}' not found.")
        return ref_coords.to(config.DEVICE), {"reference_source": "native", "reference_path": None}

    if src not in ("external", "external_coords"):
        raise ValueError("reference_source must be one of: native, external")
    if not external_manifest:
        raise ValueError("external manifest is required for reference_source=external")

    row = _resolve_manifest_entry(external_manifest, target)
    if row is None:
        raise KeyError(f"No external manifest row found for target '{target}'")

    path_val = str(row.get("path", "")).strip()
    if not path_val:
        raise ValueError(f"Manifest row for '{target}' must include non-empty 'path'")
    key_val = row.get("key", external_key)
    frame_val = row.get("frame", external_frame)
    frame_i = int(frame_val) if frame_val is not None else int(external_frame)
    coords = _load_coords_file(path=path_val, key=key_val, frame=frame_i)
    meta = {
        "reference_source": "external",
        "reference_path": os.path.abspath(path_val),
        "reference_key": key_val,
        "reference_frame": frame_i,
        "reference_engine": row.get("engine"),
        "reference_label": row.get("label"),
        "reference_representation": _normalize_representation(row.get("representation", "")),
        "reference_bead_order": _normalize_bead_order(row.get("bead_order", "")),
        "reference_n_atoms": int(coords.shape[0]),
    }
    return coords, meta


def benchmark_accuracy(
    target: str,
    refinement_steps: int = 1000,
    num_runs: int = 5,
    reference_source: str = "native",
    noise_scale: float = 0.02,
    seed_base: int = 42,
    external_manifest: Optional[Dict[str, Dict[str, Any]]] = None,
    external_key: Optional[str] = None,
    external_frame: int = -1,
    compare_bead: str = "auto",
    target_refinement_override: Optional[Dict[str, Any]] = None,
    simulate_explicit_2bead: bool = False,
    simulation_engine: str = "refinement",
    benchmark_warmup_steps: int = 40,
    benchmark_replicas: int = 1,
    benchmark_force_backend: str = "auto",
    benchmark_neighbor_settings: Optional[Dict[str, Any]] = None,
    benchmark_force_clip: float = 200.0,
    benchmark_ai_correction_clip: float = 100.0,
    use_ai_router: bool = False,
    ai_interval: int = 1,
    ai_router_checkpoint: Optional[str] = None,
    ai_router_checkpoint_strict: bool = False,
    ai_collect_aux: bool = False,
) -> Dict[str, Any]:
    """
    내부 결과(run_target)와 기준 reference(native 또는 external coords)를 직접 비교.
    """
    sim_engine = str(simulation_engine).strip().lower()
    if sim_engine not in ("refinement", "benchmark"):
        raise ValueError("simulation_engine must be one of: refinement, benchmark")
    print(
        f"Benchmarking accuracy for {target} over {refinement_steps} steps "
        f"({num_runs} runs, ref={reference_source}, engine={sim_engine}, ai={bool(use_ai_router)})"
    )
    ref_coords, ref_meta = _load_reference_coords(
        target=target,
        reference_source=reference_source,
        external_manifest=external_manifest,
        external_key=external_key,
        external_frame=external_frame,
    )
    native_coords, _ = load_native_structure(target)
    native_coords = native_coords.to(config.DEVICE) if native_coords is not None else None

    all_rmsd_vs_ref_raw: List[float] = []
    all_rmsd_vs_ref_aligned: List[float] = []
    all_rmsd_vs_native_raw: List[float] = []
    all_rmsd_vs_native_aligned: List[float] = []
    all_rg: List[float] = []
    comparison_projection = "none"
    ai_checkpoint_loaded_any = False
    ai_checkpoint_loaded_all = True
    ai_checkpoint_path = _optional_str(ai_router_checkpoint)
    ref_vs_native_raw: Optional[float] = None
    ref_vs_native_aligned: Optional[float] = None
    if native_coords is not None and native_coords.shape == ref_coords.shape:
        ref_vs_native_raw = calculate_rmsd(ref_coords, native_coords)
        ref_vs_native_aligned = calculate_rmsd_aligned(ref_coords, native_coords)
    refinement_kwargs = _to_refinement_kwargs(target_refinement_override)
    bench_neighbor_settings = dict(benchmark_neighbor_settings or {})

    for run in range(int(num_runs)):
        print(f"  Run {run + 1}/{num_runs}")
        run_seed = int(seed_base) + run
        if sim_engine == "benchmark":
            perf = benchmark_simulation(
                target=target,
                steps=int(refinement_steps),
                use_ai_router=bool(use_ai_router),
                num_runs=1,
                warmup_steps=int(benchmark_warmup_steps),
                batch_replicas=int(benchmark_replicas),
                ai_interval=max(int(ai_interval), 1),
                output_file=None,
                neighbor_settings=bench_neighbor_settings,
                force_backend=str(benchmark_force_backend),
                random_seed=int(run_seed),
                ai_collect_aux=bool(ai_collect_aux),
                capture_final_coords=True,
                ai_router_checkpoint=ai_checkpoint_path,
                ai_router_checkpoint_strict=bool(ai_router_checkpoint_strict),
                initial_noise_scale=float(noise_scale),
                force_clip=float(benchmark_force_clip),
                ai_correction_clip=float(benchmark_ai_correction_clip),
            )
            final_coords = np.asarray(perf.get("final_coords"), dtype=np.float32)
            if final_coords.ndim != 3 or final_coords.shape[0] < 1:
                raise RuntimeError(
                    f"benchmark_simulation did not return expected final_coords [B,N,3], got {final_coords.shape}"
                )
            simulated_coords = torch.as_tensor(final_coords[0], dtype=torch.float32, device=config.DEVICE)
            loaded_flag = bool(perf.get("ai_router_checkpoint_loaded", False))
            ai_checkpoint_loaded_any = ai_checkpoint_loaded_any or loaded_flag
            ai_checkpoint_loaded_all = ai_checkpoint_loaded_all and loaded_flag
        else:
            simulated_coords = run_target(
                target,
                steps=int(refinement_steps),
                noise_scale=float(noise_scale),
                seed=int(run_seed),
                return_metrics=False,
                **refinement_kwargs,
            ).to(config.DEVICE)
        if bool(simulate_explicit_2bead) and simulated_coords.shape[0] * 2 == ref_coords.shape[0]:
            simulated_coords = _expand_ca_to_explicit_2bead(simulated_coords)

        sim_cmp, ref_cmp, projection_note = _reconcile_compare_coords(
            simulated_coords=simulated_coords,
            reference_coords=ref_coords,
            reference_meta=ref_meta,
            compare_bead=str(compare_bead),
        )
        comparison_projection = projection_note

        if sim_cmp.shape != ref_cmp.shape:
            raise ValueError(
                f"Shape mismatch target={target}: simulated={tuple(sim_cmp.shape)} "
                f"vs reference={tuple(ref_cmp.shape)}"
            )

        rmsd_ref_raw = calculate_rmsd(sim_cmp, ref_cmp)
        rmsd_ref_aligned = calculate_rmsd_aligned(sim_cmp, ref_cmp)
        rg = calculate_radius_of_gyration(sim_cmp)
        all_rmsd_vs_ref_raw.append(rmsd_ref_raw)
        all_rmsd_vs_ref_aligned.append(rmsd_ref_aligned)
        all_rg.append(rg)

        if native_coords is not None and native_coords.shape == sim_cmp.shape:
            all_rmsd_vs_native_raw.append(calculate_rmsd(sim_cmp, native_coords))
            all_rmsd_vs_native_aligned.append(calculate_rmsd_aligned(sim_cmp, native_coords))

        print(
            f"    Run {run + 1} RMSD(ref,raw): {rmsd_ref_raw:.4f}, "
            f"RMSD(ref,aligned): {rmsd_ref_aligned:.4f}, Rg: {rg:.4f}"
        )

    avg_rmsd_raw = float(np.mean(all_rmsd_vs_ref_raw))
    std_rmsd_raw = float(np.std(all_rmsd_vs_ref_raw))
    avg_rmsd_aligned = float(np.mean(all_rmsd_vs_ref_aligned))
    std_rmsd_aligned = float(np.std(all_rmsd_vs_ref_aligned))

    results = {
        "target": target,
        "refinement_steps": int(refinement_steps),
        "num_runs": int(num_runs),
        "reference_source": ref_meta.get("reference_source", reference_source),
        "reference_path": ref_meta.get("reference_path"),
        "reference_key": ref_meta.get("reference_key"),
        "reference_frame": ref_meta.get("reference_frame"),
        "reference_engine": ref_meta.get("reference_engine"),
        "reference_label": ref_meta.get("reference_label"),
        "reference_representation": ref_meta.get("reference_representation"),
        "reference_bead_order": ref_meta.get("reference_bead_order"),
        "comparison_bead_mode": str(compare_bead),
        "comparison_projection": str(comparison_projection),
        # Backward-compatible aliases (raw RMSD).
        "avg_rmsd": avg_rmsd_raw,
        "std_rmsd": std_rmsd_raw,
        "avg_rmsd_raw": avg_rmsd_raw,
        "std_rmsd_raw": std_rmsd_raw,
        "avg_rmsd_aligned": avg_rmsd_aligned,
        "std_rmsd_aligned": std_rmsd_aligned,
        "avg_rg": float(np.mean(all_rg)),
        "std_rg": float(np.std(all_rg)),
        # Backward-compatible aliases (raw RMSD vs native).
        "avg_rmsd_vs_native": float(np.mean(all_rmsd_vs_native_raw)) if all_rmsd_vs_native_raw else None,
        "std_rmsd_vs_native": float(np.std(all_rmsd_vs_native_raw)) if all_rmsd_vs_native_raw else None,
        "avg_rmsd_vs_native_raw": float(np.mean(all_rmsd_vs_native_raw)) if all_rmsd_vs_native_raw else None,
        "std_rmsd_vs_native_raw": float(np.std(all_rmsd_vs_native_raw)) if all_rmsd_vs_native_raw else None,
        "avg_rmsd_vs_native_aligned": (
            float(np.mean(all_rmsd_vs_native_aligned)) if all_rmsd_vs_native_aligned else None
        ),
        "std_rmsd_vs_native_aligned": (
            float(np.std(all_rmsd_vs_native_aligned)) if all_rmsd_vs_native_aligned else None
        ),
        # Backward-compatible alias (raw).
        "avg_reference_vs_native_rmsd": ref_vs_native_raw,
        "avg_reference_vs_native_rmsd_raw": ref_vs_native_raw,
        "avg_reference_vs_native_rmsd_aligned": ref_vs_native_aligned,
        "target_override_applied": bool(refinement_kwargs),
        "target_override_refinement_dt": refinement_kwargs.get("refinement_dt"),
        "target_override_restraint_k": refinement_kwargs.get("restraint_k"),
        "target_override_force_clip": refinement_kwargs.get("force_clip"),
        "simulate_explicit_2bead": bool(simulate_explicit_2bead),
        "simulation_engine": sim_engine,
        "use_ai_router": bool(use_ai_router) if sim_engine == "benchmark" else False,
        "ai_interval": int(max(int(ai_interval), 1)),
        "benchmark_warmup_steps": int(benchmark_warmup_steps),
        "benchmark_replicas": int(max(int(benchmark_replicas), 1)),
        "benchmark_force_backend": str(benchmark_force_backend),
        "benchmark_neighbor_settings": json.dumps(bench_neighbor_settings, ensure_ascii=False),
        "benchmark_force_clip": float(benchmark_force_clip),
        "benchmark_ai_correction_clip": float(benchmark_ai_correction_clip),
        "ai_router_checkpoint": ai_checkpoint_path,
        "ai_router_checkpoint_strict": bool(ai_router_checkpoint_strict),
        "ai_router_checkpoint_loaded_any": bool(ai_checkpoint_loaded_any),
        "ai_router_checkpoint_loaded_all": bool(ai_checkpoint_loaded_all) if ai_checkpoint_path else None,
    }
    return results


def compare_accuracy_vs_external(
    target: str,
    our_results: Dict[str, Any],
    external_results_file: str,
) -> Dict[str, Any]:
    """
    내부 결과와 외부 결과 요약 CSV를 비교.
    CSV columns: target, avg_rmsd, avg_rg
    """
    ext_df = pd.read_csv(external_results_file)
    ext_row = ext_df[ext_df["target"] == target]
    if ext_row.empty:
        print(f"Warning: No external results found for {target} in {external_results_file}")
        return {}

    ext_rmsd = float(ext_row["avg_rmsd"].iloc[0])
    ext_rg = float(ext_row["avg_rg"].iloc[0])
    return {
        "target": target,
        "our_avg_rmsd": float(our_results.get("avg_rmsd", float("nan"))),
        "external_avg_rmsd": ext_rmsd,
        "rmsd_difference": float(our_results.get("avg_rmsd", float("nan"))) - ext_rmsd,
        "our_avg_rg": float(our_results.get("avg_rg", float("nan"))),
        "external_avg_rg": ext_rg,
        "rg_difference": float(our_results.get("avg_rg", float("nan"))) - ext_rg,
    }


def _external_summary_map(path: Optional[str]) -> Dict[str, Dict[str, Any]]:
    if not path:
        return {}
    if not os.path.exists(path):
        raise FileNotFoundError(f"external summary csv not found: {path}")
    df = pd.read_csv(path)
    out: Dict[str, Dict[str, Any]] = {}
    for _, row in df.iterrows():
        target = str(row.get("target", "")).strip()
        if not target:
            continue
        out[_normalize_target_key(target)] = row.to_dict()
    return out


def _load_target_profile(path: Optional[str]) -> Dict[str, Dict[str, Any]]:
    if not path:
        return {}
    path_i = os.path.abspath(str(path))
    if not os.path.exists(path_i):
        raise FileNotFoundError(f"target profile json not found: {path_i}")
    with open(path_i, "r", encoding="utf-8") as f:
        payload = json.load(f)
    targets = payload.get("targets", {}) if isinstance(payload, dict) else {}
    if not isinstance(targets, dict):
        raise ValueError(f"target profile json must include targets object: {path_i}")
    out: Dict[str, Dict[str, Any]] = {}
    for target, cfg in targets.items():
        if not isinstance(cfg, dict):
            continue
        out[_normalize_target_key(target)] = dict(cfg)
    return out


def _to_refinement_kwargs(target_override: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(target_override, dict):
        return {}
    out: Dict[str, Any] = {}
    if "refinement_dt" in target_override:
        out["refinement_dt"] = float(target_override["refinement_dt"])
    elif "dt" in target_override:
        out["refinement_dt"] = float(target_override["dt"])
    if "restraint_k" in target_override:
        out["restraint_k"] = float(target_override["restraint_k"])
    if "force_clip" in target_override:
        out["force_clip"] = float(target_override["force_clip"])
    return out


def run_accuracy_report(args: argparse.Namespace) -> Dict[str, Any]:
    targets = _parse_targets(args.targets)
    manifest = None
    if str(args.reference_source).lower() in ("external", "external_coords"):
        if not args.external_manifest:
            raise ValueError("--external-manifest is required when --reference-source=external")
        manifest = _read_external_manifest(args.external_manifest)
    ext_summary = _external_summary_map(args.external_summary_csv)
    target_profile_map = _load_target_profile(getattr(args, "target_profile_json", None))
    benchmark_neighbor_settings = _parse_neighbor_settings(
        str(getattr(args, "benchmark_neighbor_settings", ""))
    )

    rows: List[Dict[str, Any]] = []
    for target in targets:
        target_override = target_profile_map.get(_normalize_target_key(target))
        row = benchmark_accuracy(
            target=target,
            refinement_steps=int(args.steps),
            num_runs=int(args.runs),
            reference_source=str(args.reference_source),
            noise_scale=float(args.noise),
            seed_base=int(args.seed_base),
            external_manifest=manifest,
            external_key=args.external_key,
            external_frame=int(args.external_frame),
            compare_bead=str(getattr(args, "compare_bead", "auto")),
            target_refinement_override=target_override,
            simulate_explicit_2bead=bool(getattr(args, "simulate_explicit_2bead", False)),
            simulation_engine=str(getattr(args, "simulation_engine", "refinement")),
            benchmark_warmup_steps=int(getattr(args, "benchmark_warmup_steps", 40)),
            benchmark_replicas=int(getattr(args, "benchmark_replicas", 1)),
            benchmark_force_backend=str(getattr(args, "benchmark_force_backend", "auto")),
            benchmark_neighbor_settings=benchmark_neighbor_settings,
            benchmark_force_clip=float(getattr(args, "benchmark_force_clip", 200.0)),
            benchmark_ai_correction_clip=float(getattr(args, "benchmark_ai_correction_clip", 100.0)),
            use_ai_router=bool(getattr(args, "use_ai_router", False)),
            ai_interval=int(getattr(args, "ai_interval", 1)),
            ai_router_checkpoint=_optional_str(getattr(args, "ai_router_checkpoint", "")),
            ai_router_checkpoint_strict=bool(getattr(args, "ai_router_checkpoint_strict", False)),
            ai_collect_aux=bool(getattr(args, "ai_collect_aux", False)),
        )

        summary_row = ext_summary.get(_normalize_target_key(target))
        if summary_row:
            ext_avg_rmsd = summary_row.get("avg_rmsd")
            ext_avg_rmsd_aligned = summary_row.get("avg_rmsd_aligned")
            ext_avg_rg = summary_row.get("avg_rg")
            row["external_avg_rmsd"] = float(ext_avg_rmsd) if pd.notna(ext_avg_rmsd) else None
            row["external_avg_rmsd_aligned"] = (
                float(ext_avg_rmsd_aligned) if pd.notna(ext_avg_rmsd_aligned) else None
            )
            row["external_avg_rg"] = float(ext_avg_rg) if pd.notna(ext_avg_rg) else None
            row["delta_vs_external_avg_rmsd"] = (
                row["avg_rmsd"] - row["external_avg_rmsd"]
                if row.get("external_avg_rmsd") is not None
                else None
            )
            row["delta_vs_external_avg_rmsd_aligned"] = (
                row["avg_rmsd_aligned"] - row["external_avg_rmsd_aligned"]
                if row.get("external_avg_rmsd_aligned") is not None
                else None
            )
            row["delta_vs_external_avg_rg"] = (
                row["avg_rg"] - row["external_avg_rg"]
                if row.get("external_avg_rg") is not None
                else None
            )
        rows.append(row)

    out_csv = str(args.out_csv)
    out_json = str(args.out_json)
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)

    df = pd.DataFrame(rows)
    df.to_csv(out_csv, index=False)

    payload = {
        "summary": {
            "targets": len(rows),
            "reference_source": str(args.reference_source),
            "compare_bead": str(getattr(args, "compare_bead", "auto")),
            "simulate_explicit_2bead": bool(getattr(args, "simulate_explicit_2bead", False)),
            "simulation_engine": str(getattr(args, "simulation_engine", "refinement")),
            "use_ai_router": bool(getattr(args, "use_ai_router", False)),
            "ai_interval": int(getattr(args, "ai_interval", 1)),
            "benchmark_warmup_steps": int(getattr(args, "benchmark_warmup_steps", 40)),
            "benchmark_replicas": int(getattr(args, "benchmark_replicas", 1)),
            "benchmark_force_backend": str(getattr(args, "benchmark_force_backend", "auto")),
            "benchmark_neighbor_settings": benchmark_neighbor_settings,
            "benchmark_force_clip": float(getattr(args, "benchmark_force_clip", 200.0)),
            "benchmark_ai_correction_clip": float(getattr(args, "benchmark_ai_correction_clip", 100.0)),
            "ai_router_checkpoint": _optional_str(getattr(args, "ai_router_checkpoint", "")),
            "ai_router_checkpoint_strict": bool(getattr(args, "ai_router_checkpoint_strict", False)),
            "ai_router_checkpoint_loaded_targets": int(
                sum(1 for row in rows if bool(row.get("ai_router_checkpoint_loaded_any", False)))
            ),
            "target_profile_json": (
                os.path.abspath(str(args.target_profile_json))
                if getattr(args, "target_profile_json", None)
                else None
            ),
            "target_overrides_applied": int(
                sum(1 for row in rows if bool(row.get("target_override_applied", False)))
            ),
            "avg_rmsd": float(df["avg_rmsd"].mean()) if not df.empty else None,
            "avg_rmsd_raw": float(df["avg_rmsd_raw"].mean()) if ("avg_rmsd_raw" in df.columns and not df.empty) else None,
            "avg_rmsd_aligned": (
                float(df["avg_rmsd_aligned"].mean()) if ("avg_rmsd_aligned" in df.columns and not df.empty) else None
            ),
            "avg_rg": float(df["avg_rg"].mean()) if not df.empty else None,
            "avg_rmsd_vs_native": (
                float(df["avg_rmsd_vs_native"].dropna().mean())
                if ("avg_rmsd_vs_native" in df.columns and not df["avg_rmsd_vs_native"].dropna().empty)
                else None
            ),
            "avg_rmsd_vs_native_aligned": (
                float(df["avg_rmsd_vs_native_aligned"].dropna().mean())
                if ("avg_rmsd_vs_native_aligned" in df.columns and not df["avg_rmsd_vs_native_aligned"].dropna().empty)
                else None
            ),
        },
        "rows": rows,
    }
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(json.dumps(payload["summary"], indent=2))
    print(f"Wrote CSV: {out_csv}")
    print(f"Wrote JSON: {out_json}")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run accuracy benchmarks vs native or external MD references."
    )
    parser.add_argument("--targets", type=str, default="all", help="all or CSV target names")
    parser.add_argument("--steps", type=int, default=1000, help="Refinement steps per run")
    parser.add_argument("--runs", type=int, default=5, help="Number of runs")
    parser.add_argument("--noise", type=float, default=0.02, help="Noise scale for initial perturbation")
    parser.add_argument("--seed-base", type=int, default=42, help="Base seed for run reproducibility")
    parser.add_argument(
        "--reference-source",
        type=str,
        default="native",
        choices=["native", "external", "external_coords"],
        help="Reference source for direct RMSD comparison",
    )
    parser.add_argument(
        "--external-manifest",
        type=str,
        default=None,
        help="CSV/JSON mapping target->external coordinate file path (required for external mode)",
    )
    parser.add_argument(
        "--external-key",
        type=str,
        default=None,
        help="Optional NPZ key default; row-level key in manifest overrides this",
    )
    parser.add_argument(
        "--external-frame",
        type=int,
        default=-1,
        help="Frame index for [T,N,3] arrays; -1 picks last frame",
    )
    parser.add_argument(
        "--external-summary-csv",
        type=str,
        default=None,
        help="Optional external summary CSV (target,avg_rmsd,avg_rg) for delta reporting",
    )
    parser.add_argument(
        "--compare-bead",
        type=str,
        default="auto",
        choices=["auto", "ca", "all"],
        help="When shapes differ (e.g., external 2-bead vs internal CA), choose auto CA projection or strict all-bead compare.",
    )
    parser.add_argument(
        "--simulate-explicit-2bead",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Expand simulated CA output to explicit CA+SC [2N,3] before comparison when reference is 2-bead.",
    )
    parser.add_argument(
        "--target-profile-json",
        type=str,
        default=None,
        help="Optional per-target refinement profile JSON (dt/restraint_k/force_clip).",
    )
    parser.add_argument(
        "--simulation-engine",
        type=str,
        default="refinement",
        choices=["refinement", "benchmark"],
        help="refinement(run_target) or benchmark(benchmark_simulation)",
    )
    parser.add_argument(
        "--use-ai-router",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Only used with --simulation-engine benchmark",
    )
    parser.add_argument(
        "--ai-interval",
        type=int,
        default=1,
        help="AI correction interval for benchmark engine",
    )
    parser.add_argument("--benchmark-warmup-steps", type=int, default=40)
    parser.add_argument("--benchmark-replicas", type=int, default=1)
    parser.add_argument(
        "--benchmark-force-backend",
        type=str,
        default="auto",
        choices=["auto", "pytorch"],
        help="Force backend for benchmark engine",
    )
    parser.add_argument(
        "--benchmark-neighbor-settings",
        type=str,
        default="grid_spacing=12,cutoff=12,skin=2,max_neighbors=100,rebuild_stride=4,max_atoms_per_cell=64",
        help="Comma-separated key=value neighbor settings for benchmark engine",
    )
    parser.add_argument(
        "--benchmark-force-clip",
        type=float,
        default=200.0,
        help="Absolute clip for total force in benchmark engine. <=0 disables clipping.",
    )
    parser.add_argument(
        "--benchmark-ai-correction-clip",
        type=float,
        default=100.0,
        help="Absolute clip for AI correction force in benchmark engine. <=0 disables clipping.",
    )
    parser.add_argument("--ai-router-checkpoint", type=str, default="")
    parser.add_argument(
        "--ai-router-checkpoint-strict",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    parser.add_argument(
        "--ai-collect-aux",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Collect AIRouter aux/debug outputs during benchmark inference",
    )
    parser.add_argument("--out-csv", type=str, default="runs/accuracy_external_report.csv")
    parser.add_argument("--out-json", type=str, default="runs/accuracy_external_report.json")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    run_accuracy_report(args)


if __name__ == "__main__":
    main()
