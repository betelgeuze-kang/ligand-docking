#!/usr/bin/env python3

from __future__ import annotations

import argparse
import glob
import json
import os
import re
from typing import Any, Dict, List, Optional, Sequence

import h5py
import numpy as np
import pandas as pd
import torch

from core.definitions import ResearchConstants
from core.forcefield import ForceField
from core.topology import TopologyFactory

OPTIONAL_SCALAR_FIELDS = (
    "energy",
    "Rg",
    "compactness",
    "sasa",
    "cluster_max",
    "is_llps",
    "is_folded",
    "rmsd",
    "ionic_strength",
    "ptm_count",
    "force_scale",
    "cooling_rate",
    "hydro_strength",
    "k_angle",
    "theta0",
    "k_dihedral",
    "phi0_alpha",
    "violations",
    "ai_correction_active",
    "temp",
    "salt_conc",
    "pH",
)


def _normalize_target_key(name: str) -> str:
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


def _parse_targets(spec: str) -> List[str]:
    if str(spec).strip().lower() == "all":
        return list(ResearchConstants.CHALLENGES.keys())
    return [x.strip() for x in str(spec).split(",") if x.strip()]


def _parse_float_dtype(spec: str) -> np.dtype:
    s = str(spec).strip().lower()
    if s in ("float16", "fp16", "half"):
        return np.float16
    if s in ("float32", "fp32", "single"):
        return np.float32
    raise ValueError(f"unsupported float dtype: {spec}")


def _infer_split_from_path(path: str) -> str:
    name = os.path.basename(path).lower()
    m = re.search(r"_airouter_(train|val|test)_data\.h5$", name)
    if m:
        return str(m.group(1))
    return "unknown"


def _infer_target_from_path(path: str) -> Optional[str]:
    base = os.path.basename(path)
    norm_base = _normalize_target_key(base)
    for target in ResearchConstants.CHALLENGES.keys():
        if _normalize_target_key(target) in norm_base:
            return target
    return None


def _target_from_h5(path: str, f: h5py.File) -> str:
    attr_target = f.attrs.get("target")
    if attr_target is not None:
        t = str(attr_target).strip()
        if t:
            return t
    t2 = _infer_target_from_path(path)
    if t2:
        return t2
    raise ValueError(f"could not infer target from file: {path}")


def _expand_residue_types_if_needed(residue_types: np.ndarray, n_atoms: int) -> np.ndarray:
    r = np.asarray(residue_types)
    if r.ndim == 1:
        rr = r
    elif r.ndim == 2 and r.shape[0] == 1:
        rr = r[0]
    else:
        raise ValueError(f"residue_types shape must be [N] or [1,N], got {r.shape}")

    if rr.shape[0] == n_atoms:
        return rr
    if n_atoms == rr.shape[0] * 2:
        return np.repeat(rr, 2)
    raise ValueError(f"residue_types length mismatch: n_atoms={n_atoms}, residue_types={rr.shape[0]}")


def _pick_indices(n_total: int, max_samples: Optional[int]) -> np.ndarray:
    if max_samples is None or int(max_samples) <= 0 or int(max_samples) >= int(n_total):
        return np.arange(n_total, dtype=np.int64)
    k = int(max_samples)
    if k == 1:
        return np.asarray([n_total - 1], dtype=np.int64)
    return np.linspace(0, n_total - 1, num=k, dtype=np.int64)


def _target_allowed(target: str, selected_targets: List[str]) -> bool:
    allowed = {_normalize_target_key(t) for t in selected_targets}
    return _normalize_target_key(target) in allowed


def _ensure_parent(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


class _ReferenceResidualRepairer:
    """
    Recomputes reference force on stored coordinates and builds residual:
      residual = reference_force - stored_physics_force
    """

    def __init__(
        self,
        target: str,
        device: str = "cpu",
        reference_cutoff: float = 14.0,
        reference_max_neighbors: int = 160,
        reference_force_cap: Optional[float] = 100.0,
    ):
        conf = ResearchConstants.CHALLENGES.get(target)
        if conf is None:
            raise ValueError(f"unknown target for residual repair: {target}")
        self.target = target
        self.device = torch.device(str(device))
        self.reference_cutoff = float(reference_cutoff)
        self.reference_max_neighbors = int(reference_max_neighbors)
        self.reference_force_cap = (
            None if reference_force_cap is None else float(reference_force_cap)
        )
        top = TopologyFactory(
            int(conf["n_res"]),
            str(conf["type"]),
            conf["box"],
            self.device,
            target_name=target,
        )
        ff_params = {"d_e": 20.0, "eps_solv": 25.0, "sigma": 3.8, "r0": 4.2}
        self.ff = ForceField(top, params=ff_params, force_backend="pytorch").to(self.device)

    def compute(self, coords: np.ndarray, physics_forces: np.ndarray) -> np.ndarray:
        c = torch.from_numpy(np.asarray(coords, dtype=np.float32)).unsqueeze(0).to(self.device)
        with torch.no_grad():
            f_ref, _ = self.ff.compute_reference_pytorch(
                c,
                cutoff=self.reference_cutoff,
                max_neighbors=self.reference_max_neighbors,
                skin=0.0,
            )
            if self.reference_force_cap is not None and self.reference_force_cap > 0.0:
                max_force_mag = float(f_ref.norm(dim=-1).max().item())
                if max_force_mag > self.reference_force_cap:
                    scale = float(self.reference_force_cap / max_force_mag)
                    f_ref = f_ref * scale
        f_ref_np = f_ref.squeeze(0).detach().cpu().numpy().astype(np.float32, copy=False)
        f_phy_np = np.asarray(physics_forces, dtype=np.float32)
        return f_ref_np - f_phy_np


def _distill_one_h5(
    path: str,
    out_dir: str,
    float_dtype: np.dtype,
    keep_coords: bool,
    max_samples_per_file: Optional[int],
    min_quality: Optional[float],
    skip_if_exists: bool,
    repair_zero_residual: bool,
    zero_residual_atol: float,
    repair_device: str,
    repair_reference_cutoff: float,
    repair_reference_max_neighbors: int,
    repair_reference_force_cap: Optional[float],
) -> Dict[str, Any]:
    with h5py.File(path, "r") as f:
        target = _target_from_h5(path, f)
        split = _infer_split_from_path(path)
        residual_mode_attr = bool(f.attrs.get("residual_mode", False))
        n_total = int(f["coords"].shape[0])
        selected_idx = _pick_indices(n_total, max_samples_per_file)

        out_name = f"{_normalize_target_key(target)}_{split}_distilled_residual.npz"
        out_path = os.path.join(out_dir, out_name)
        _ensure_parent(out_path)
        if skip_if_exists and os.path.exists(out_path):
            return {
                "target": target,
                "split": split,
                "input_h5": path,
                "output_npz": out_path,
                "input_bytes": int(os.path.getsize(path)),
                "output_bytes": int(os.path.getsize(out_path)),
                "samples_total": n_total,
                "samples_selected": None,
                "samples_saved": None,
                "residual_source": "cached_existing",
                "skipped": True,
            }

        coords_list: List[np.ndarray] = []
        residual_list: List[np.ndarray] = []
        residue_types_list: List[np.ndarray] = []
        quality_list: List[np.ndarray] = []
        sample_idx_saved: List[int] = []

        has_quality = "quality_score" in f
        has_physics = "physics_forces" in f
        has_target = "target_forces" in f
        if not has_target:
            raise ValueError(f"missing required dataset 'target_forces' in {path}")
        scalar_field_arrays: Dict[str, Any] = {}
        scalar_lists: Dict[str, List[float]] = {}
        for key in OPTIONAL_SCALAR_FIELDS:
            if key not in f:
                continue
            arr = f[key]
            if int(arr.shape[0]) != int(n_total):
                continue
            scalar_field_arrays[key] = arr
            scalar_lists[key] = []
        repairer: Optional[_ReferenceResidualRepairer] = None
        if repair_zero_residual and has_physics:
            repairer = _ReferenceResidualRepairer(
                target=target,
                device=repair_device,
                reference_cutoff=repair_reference_cutoff,
                reference_max_neighbors=repair_reference_max_neighbors,
                reference_force_cap=repair_reference_force_cap,
            )
        zero_like_before_repair = 0
        repaired_nonzero_samples = 0
        zero_like_after_repair = 0

        # Stream sample-by-sample to avoid loading full trajectory in memory.
        for idx in selected_idx.tolist():
            coords_i = np.asarray(f["coords"][idx], dtype=np.float32)
            target_i = np.asarray(f["target_forces"][idx], dtype=np.float32)
            if has_physics and not residual_mode_attr:
                physics_i = np.asarray(f["physics_forces"][idx], dtype=np.float32)
                residual_i = target_i - physics_i
                residual_source = "target_forces_minus_physics_forces"
            else:
                physics_i = None
                residual_i = target_i
                residual_source = "target_forces_direct"
            max_abs_before = float(np.max(np.abs(residual_i))) if residual_i.size else 0.0
            if max_abs_before <= float(zero_residual_atol):
                zero_like_before_repair += 1
                if repairer is not None and physics_i is not None:
                    residual_i = repairer.compute(coords_i, physics_i)
                    residual_source = "target_forces_minus_physics_forces_repaired_reference"
                    max_abs_after = float(np.max(np.abs(residual_i))) if residual_i.size else 0.0
                    if max_abs_after > float(zero_residual_atol):
                        repaired_nonzero_samples += 1
                    else:
                        zero_like_after_repair += 1

            if has_quality:
                q_i = float(np.asarray(f["quality_score"][idx]).item())
            else:
                q_i = 1.0
            if min_quality is not None and q_i < float(min_quality):
                continue

            residue_i = np.asarray(f["residue_types"][idx], dtype=np.int32)
            residue_i = _expand_residue_types_if_needed(residue_i, n_atoms=int(coords_i.shape[0]))

            if keep_coords:
                coords_list.append(coords_i.astype(float_dtype, copy=False))
            residual_list.append(residual_i.astype(float_dtype, copy=False))
            residue_types_list.append(residue_i.astype(np.int16, copy=False))
            quality_list.append(np.asarray(q_i, dtype=np.float32))
            for key, arr in scalar_field_arrays.items():
                scalar_lists[key].append(float(np.asarray(arr[idx]).item()))
            sample_idx_saved.append(int(idx))

        if len(residual_list) == 0:
            raise ValueError(f"no samples survived filtering for {path}")

        payload: Dict[str, Any] = {
            "residual_forces": np.stack(residual_list, axis=0),
            "residue_types": np.stack(residue_types_list, axis=0),
            "quality_score": np.asarray(quality_list, dtype=np.float32),
            "sample_index": np.asarray(sample_idx_saved, dtype=np.int32),
        }
        if keep_coords:
            payload["coords"] = np.stack(coords_list, axis=0)
        for key, vals in scalar_lists.items():
            if len(vals) != int(len(sample_idx_saved)):
                continue
            payload[key] = np.asarray(vals, dtype=np.float32)

        np.savez_compressed(out_path, **payload)

        input_bytes = int(os.path.getsize(path))
        output_bytes = int(os.path.getsize(out_path))
        saved = int(len(sample_idx_saved))
        n_atoms = int(payload["residual_forces"].shape[1])
        n_res = int(ResearchConstants.CHALLENGES.get(target, {}).get("n_res", -1))

        return {
            "target": target,
            "split": split,
            "input_h5": path,
            "output_npz": out_path,
            "input_bytes": input_bytes,
            "output_bytes": output_bytes,
            "compression_ratio_input_over_output": float(input_bytes / max(output_bytes, 1)),
            "samples_total": int(n_total),
            "samples_selected": int(len(selected_idx)),
            "samples_saved": saved,
            "n_atoms": n_atoms,
            "n_res_expected": n_res,
            "residual_source": residual_source,
            "residual_mode_attr": bool(residual_mode_attr),
            "zero_like_before_repair": int(zero_like_before_repair),
            "repaired_nonzero_samples": int(repaired_nonzero_samples),
            "zero_like_after_repair": int(zero_like_after_repair),
            "keep_coords": bool(keep_coords),
            "float_dtype": str(np.dtype(float_dtype)),
            "skipped": False,
        }


def build_distilled_residual_dataset(
    input_glob: str,
    targets: str,
    out_dir: str,
    out_manifest_csv: str,
    out_summary_json: str,
    float_dtype: str = "float16",
    keep_coords: bool = True,
    max_samples_per_file: Optional[int] = None,
    min_quality: Optional[float] = None,
    skip_if_exists: bool = True,
    repair_zero_residual: bool = False,
    zero_residual_atol: float = 1e-8,
    repair_device: str = "cpu",
    repair_reference_cutoff: float = 14.0,
    repair_reference_max_neighbors: int = 160,
    repair_reference_force_cap: Optional[float] = 100.0,
) -> Dict[str, Any]:
    files = sorted(glob.glob(input_glob))
    if len(files) == 0:
        raise FileNotFoundError(f"no files matched input_glob: {input_glob}")
    selected_targets = _parse_targets(targets)

    _ensure_parent(out_manifest_csv)
    _ensure_parent(out_summary_json)
    os.makedirs(out_dir, exist_ok=True)

    out_rows: List[Dict[str, Any]] = []
    for path in files:
        try:
            with h5py.File(path, "r") as f:
                t = _target_from_h5(path, f)
            if not _target_allowed(t, selected_targets):
                continue
            row = _distill_one_h5(
                path=path,
                out_dir=out_dir,
                float_dtype=_parse_float_dtype(float_dtype),
                keep_coords=keep_coords,
                max_samples_per_file=max_samples_per_file,
                min_quality=min_quality,
                skip_if_exists=skip_if_exists,
                repair_zero_residual=repair_zero_residual,
                zero_residual_atol=zero_residual_atol,
                repair_device=repair_device,
                repair_reference_cutoff=repair_reference_cutoff,
                repair_reference_max_neighbors=repair_reference_max_neighbors,
                repair_reference_force_cap=repair_reference_force_cap,
            )
            out_rows.append(row)
        except Exception as exc:
            out_rows.append(
                {
                    "target": None,
                    "split": None,
                    "input_h5": path,
                    "output_npz": None,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    manifest_df = pd.DataFrame(out_rows)
    manifest_df.to_csv(out_manifest_csv, index=False)

    good_df = manifest_df[manifest_df["error"].isna()] if ("error" in manifest_df.columns) else manifest_df
    err_df = manifest_df[manifest_df["error"].notna()] if ("error" in manifest_df.columns) else pd.DataFrame()

    total_input = int(good_df["input_bytes"].fillna(0).sum()) if len(good_df) else 0
    total_output = int(good_df["output_bytes"].fillna(0).sum()) if len(good_df) else 0
    compression = float(total_input / max(total_output, 1)) if total_output > 0 else None

    summary: Dict[str, Any] = {
        "input_glob": input_glob,
        "targets": selected_targets,
        "files_matched": int(len(files)),
        "files_processed": int(len(good_df)),
        "files_failed": int(len(err_df)),
        "total_input_bytes": total_input,
        "total_output_bytes": total_output,
        "total_compression_ratio_input_over_output": compression,
        "total_samples_saved": int(good_df["samples_saved"].fillna(0).sum()) if len(good_df) else 0,
        "repair_zero_residual": bool(repair_zero_residual),
        "total_zero_like_before_repair": int(good_df["zero_like_before_repair"].fillna(0).sum()) if len(good_df) and "zero_like_before_repair" in good_df.columns else 0,
        "total_repaired_nonzero_samples": int(good_df["repaired_nonzero_samples"].fillna(0).sum()) if len(good_df) and "repaired_nonzero_samples" in good_df.columns else 0,
        "total_zero_like_after_repair": int(good_df["zero_like_after_repair"].fillna(0).sum()) if len(good_df) and "zero_like_after_repair" in good_df.columns else 0,
        "repair_reference_force_cap": (
            None if repair_reference_force_cap is None else float(repair_reference_force_cap)
        ),
        "manifest_csv": out_manifest_csv,
        "out_dir": out_dir,
        "errors": err_df[["input_h5", "error"]].to_dict(orient="records") if len(err_df) else [],
    }

    with open(out_summary_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build storage-efficient distilled residual dataset from AIRouter HDF5 files."
    )
    parser.add_argument("--input-glob", type=str, default="data/*_airouter_*_data.h5")
    parser.add_argument("--targets", type=str, default="all")
    parser.add_argument("--out-dir", type=str, default="data/distilled_residual")
    parser.add_argument("--out-manifest-csv", type=str, default="runs/distilled_residual_manifest.csv")
    parser.add_argument("--out-summary-json", type=str, default="runs/distilled_residual_summary.json")
    parser.add_argument("--float-dtype", type=str, default="float16", choices=["float16", "float32"])
    parser.add_argument("--keep-coords", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--max-samples-per-file", type=int, default=None)
    parser.add_argument("--min-quality", type=float, default=None)
    parser.add_argument("--skip-if-exists", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--repair-zero-residual", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--zero-residual-atol", type=float, default=1e-8)
    parser.add_argument("--repair-device", type=str, default="cpu")
    parser.add_argument("--repair-reference-cutoff", type=float, default=14.0)
    parser.add_argument("--repair-reference-max-neighbors", type=int, default=160)
    parser.add_argument(
        "--repair-reference-force-cap",
        type=float,
        default=100.0,
        help="Cap reference force magnitude before residual build. <=0 disables capping.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    summary = build_distilled_residual_dataset(
        input_glob=str(args.input_glob),
        targets=str(args.targets),
        out_dir=str(args.out_dir),
        out_manifest_csv=str(args.out_manifest_csv),
        out_summary_json=str(args.out_summary_json),
        float_dtype=str(args.float_dtype),
        keep_coords=bool(args.keep_coords),
        max_samples_per_file=args.max_samples_per_file,
        min_quality=args.min_quality,
        skip_if_exists=bool(args.skip_if_exists),
        repair_zero_residual=bool(args.repair_zero_residual),
        zero_residual_atol=float(args.zero_residual_atol),
        repair_device=str(args.repair_device),
        repair_reference_cutoff=float(args.repair_reference_cutoff),
        repair_reference_max_neighbors=int(args.repair_reference_max_neighbors),
        repair_reference_force_cap=(
            None
            if float(args.repair_reference_force_cap) <= 0.0
            else float(args.repair_reference_force_cap)
        ),
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
