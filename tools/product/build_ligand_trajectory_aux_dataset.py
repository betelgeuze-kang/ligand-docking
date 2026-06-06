#!/usr/bin/env python3

from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
from itertools import repeat
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


def _ensure_parent(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


def _load_csv(path: str, required: Optional[Sequence[str]] = None) -> pd.DataFrame:
    src = str(path).strip()
    if (not src) or (not os.path.exists(src)):
        raise FileNotFoundError(f"csv not found: {src}")
    df = pd.read_csv(src)
    req = set(required or [])
    if req and not req.issubset(set(df.columns)):
        raise ValueError(f"{src} missing required columns: {sorted(req - set(df.columns))}")
    return df


def _pair_key(target: Any, ligand_id: Any) -> Tuple[str, str]:
    return (str(target).strip(), str(ligand_id).strip())


def _compute_min_distance_series(protein_ca: np.ndarray, ligand_frames: np.ndarray) -> np.ndarray:
    prot = np.asarray(protein_ca, dtype=np.float32)
    lig = np.asarray(ligand_frames, dtype=np.float32)
    if prot.ndim != 2 or lig.ndim != 3 or prot.shape[0] <= 0 or lig.shape[0] <= 0:
        return np.zeros((0,), dtype=np.float32)
    mins: List[float] = []
    for frame in lig:
        diff = prot[:, None, :] - frame[None, :, :]
        d2 = np.sum(diff * diff, axis=2)
        mins.append(float(np.sqrt(np.min(d2))))
    return np.asarray(mins, dtype=np.float32)


def _centroid_series(ligand_frames: np.ndarray) -> np.ndarray:
    lig = np.asarray(ligand_frames, dtype=np.float32)
    if lig.ndim != 3 or lig.shape[0] <= 0:
        return np.zeros((0, 3), dtype=np.float32)
    return lig.mean(axis=1, dtype=np.float32)


def _extract_feature_row(
    row: Dict[str, Any],
    label_lookup: Dict[Tuple[str, str], int],
    role_lookup: Dict[Tuple[str, str], str],
) -> Dict[str, Any]:
    if bool(row.get("inline_aux_available", False)) and ("mean_min_distance_A" in row):
        target = str(row.get("target", "")).strip()
        ligand_id = str(row.get("ligand_id", "")).strip()
        key = _pair_key(target, ligand_id)
        is_binder = int(label_lookup.get(key, -1))
        role = str(role_lookup.get(key, "")).strip()
        return {
            "queue_id": str(row.get("queue_id", "")).strip(),
            "target": target,
            "ligand_id": ligand_id,
            "role": role,
            "is_binder": is_binder,
            "trajectory_npz": str(row.get("trajectory_npz", "")).strip(),
            "n_frames": int(float(row.get("trajectory_frame_count", row.get("sim_frames_count", 0)) or 0)),
            "ligand_atom_count": int(float(row.get("ligand_atom_count", 0) or 0)),
            "protein_res_count": int(float(row.get("protein_res_count", 0) or 0)),
            "frame_index_start": int(float(row.get("frame_index_start", 0) or 0)),
            "frame_index_end": int(float(row.get("frame_index_end", 0) or 0)),
            "mean_min_distance_A": float(row.get("mean_min_distance_A", 0.0) or 0.0),
            "min_min_distance_A": float(row.get("min_min_distance_A", 0.0) or 0.0),
            "final_min_distance_A": float(row.get("final_min_distance_A", 0.0) or 0.0),
            "contact_fraction_4p5A": float(row.get("contact_fraction_4p5A", 0.0) or 0.0),
            "contact_fraction_6A": float(row.get("contact_fraction_6A", 0.0) or 0.0),
            "contact_fraction_8A": float(row.get("contact_fraction_8A", 0.0) or 0.0),
            "centroid_path_A": float(row.get("centroid_path_A", 0.0) or 0.0),
            "mean_step_A": float(row.get("mean_step_A", 0.0) or 0.0),
            "max_step_A": float(row.get("max_step_A", 0.0) or 0.0),
            "centroid_dispersion_A": float(row.get("centroid_dispersion_A", 0.0) or 0.0),
            "final_shift_A": float(row.get("final_shift_A", 0.0) or 0.0),
            "affinity_hint": float(row.get("affinity_hint", 0.0) or 0.0),
            "k_attr": float(row.get("k_attr", 0.0) or 0.0),
            "protein_repulse": float(row.get("protein_repulse", 0.0) or 0.0),
            "sim_fps": float(row.get("sim_fps", row.get("sim_fps_inline", 0.0)) or 0.0),
            "quality_score": float(row.get("quality_score", row.get("contact_fraction_6A", 0.0)) or 0.0),
        }
    npz_path = str(row.get("trajectory_npz", "")).strip()
    if not npz_path or (not os.path.exists(npz_path)):
        raise FileNotFoundError(f"trajectory npz not found: {npz_path}")
    payload = np.load(npz_path, allow_pickle=False)
    protein_ca = np.asarray(payload["protein_ca"], dtype=np.float32)
    ligand_frames = np.asarray(payload["ligand_frames"], dtype=np.float32)
    frame_indices = np.asarray(payload["frame_indices"], dtype=np.int32)

    min_d = _compute_min_distance_series(protein_ca, ligand_frames)
    centroids = _centroid_series(ligand_frames)
    if centroids.shape[0] > 1:
        step = np.linalg.norm(centroids[1:] - centroids[:-1], axis=1)
    else:
        step = np.zeros((0,), dtype=np.float32)
    center_mean = centroids.mean(axis=0) if centroids.size else np.zeros((3,), dtype=np.float32)
    if centroids.size:
        dispersion = np.linalg.norm(centroids - center_mean[None, :], axis=1)
    else:
        dispersion = np.zeros((0,), dtype=np.float32)

    target = str(row.get("target", "")).strip()
    ligand_id = str(row.get("ligand_id", "")).strip()
    key = _pair_key(target, ligand_id)
    is_binder = int(label_lookup.get(key, -1))
    role = str(role_lookup.get(key, "")).strip()

    out = {
        "queue_id": str(row.get("queue_id", "")).strip(),
        "target": target,
        "ligand_id": ligand_id,
        "role": role,
        "is_binder": is_binder,
        "trajectory_npz": npz_path,
        "n_frames": int(ligand_frames.shape[0]) if ligand_frames.ndim >= 1 else 0,
        "ligand_atom_count": int(ligand_frames.shape[1]) if ligand_frames.ndim >= 2 else 0,
        "protein_res_count": int(protein_ca.shape[0]) if protein_ca.ndim >= 1 else 0,
        "frame_index_start": int(frame_indices[0]) if frame_indices.size else 0,
        "frame_index_end": int(frame_indices[-1]) if frame_indices.size else 0,
        "mean_min_distance_A": float(min_d.mean()) if min_d.size else 0.0,
        "min_min_distance_A": float(min_d.min()) if min_d.size else 0.0,
        "final_min_distance_A": float(min_d[-1]) if min_d.size else 0.0,
        "contact_fraction_4p5A": float(np.mean(min_d <= 4.5)) if min_d.size else 0.0,
        "contact_fraction_6A": float(np.mean(min_d <= 6.0)) if min_d.size else 0.0,
        "contact_fraction_8A": float(np.mean(min_d <= 8.0)) if min_d.size else 0.0,
        "centroid_path_A": float(step.sum()) if step.size else 0.0,
        "mean_step_A": float(step.mean()) if step.size else 0.0,
        "max_step_A": float(step.max()) if step.size else 0.0,
        "centroid_dispersion_A": float(dispersion.mean()) if dispersion.size else 0.0,
        "final_shift_A": float(np.linalg.norm(centroids[-1] - centroids[0])) if centroids.shape[0] >= 2 else 0.0,
        "affinity_hint": float(row.get("affinity_hint", 0.0) or 0.0),
        "k_attr": float(row.get("k_attr", 0.0) or 0.0),
        "protein_repulse": float(row.get("protein_repulse", 0.0) or 0.0),
        "sim_fps": float(row.get("sim_fps", 0.0) or 0.0),
        "quality_score": float(np.mean(min_d <= 6.0)) if min_d.size else 0.0,
    }
    return out


def _extract_feature_row_safe(
    row: Dict[str, Any],
    label_lookup: Dict[Tuple[str, str], int],
    role_lookup: Dict[Tuple[str, str], str],
) -> Tuple[bool, Dict[str, Any]]:
    try:
        return True, _extract_feature_row(row, label_lookup=label_lookup, role_lookup=role_lookup)
    except Exception as exc:
        return False, {
            "queue_id": str(row.get("queue_id", "")).strip(),
            "target": str(row.get("target", "")).strip(),
            "ligand_id": str(row.get("ligand_id", "")).strip(),
            "error": str(exc),
        }


def build_dataset(args: argparse.Namespace) -> Dict[str, Any]:
    manifest_df = _load_csv(
        str(args.stage2_manifest_csv),
        required=("queue_id", "target", "ligand_id", "status", "trajectory_npz"),
    )
    manifest_df = manifest_df[manifest_df["status"].astype(str).str.lower() == "ok"].copy()
    if bool(args.require_npz_only):
        manifest_df = manifest_df[manifest_df["trajectory_npz"].astype(str).str.len() > 0].copy()
    if int(args.max_rows) > 0:
        manifest_df = manifest_df.head(int(args.max_rows)).copy()

    label_lookup: Dict[Tuple[str, str], int] = {}
    if str(args.labels_csv).strip():
        labels_df = _load_csv(str(args.labels_csv), required=("target", "ligand_id"))
        if "is_binder" in labels_df.columns:
            for _, r in labels_df.iterrows():
                label_lookup[_pair_key(r.get("target", ""), r.get("ligand_id", ""))] = int(r.get("is_binder", 0) or 0)

    role_lookup: Dict[Tuple[str, str], str] = {}
    if str(args.split_csv).strip():
        split_df = _load_csv(str(args.split_csv), required=("target", "ligand_id", "role"))
        for _, r in split_df.iterrows():
            role_lookup[_pair_key(r.get("target", ""), r.get("ligand_id", ""))] = str(r.get("role", "")).strip()

    rows: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []
    records = manifest_df.to_dict(orient="records")
    workers_requested = int(max(0, int(getattr(args, "workers", 0))))
    workers_auto = max(1, min((os.cpu_count() or 2), 16))
    workers_used = int(workers_requested if workers_requested > 0 else workers_auto)
    parallel_threshold = int(max(1, int(getattr(args, "parallel_threshold", 128))))
    chunksize = int(max(1, int(getattr(args, "chunksize", 32))))
    parallel_enabled = bool(workers_used > 1 and len(records) >= parallel_threshold)
    if parallel_enabled:
        with cf.ProcessPoolExecutor(max_workers=workers_used) as ex:
            for ok, payload in ex.map(
                _extract_feature_row_safe,
                records,
                repeat(label_lookup),
                repeat(role_lookup),
                chunksize=chunksize,
            ):
                if ok:
                    rows.append(payload)
                else:
                    errors.append(payload)
    else:
        workers_used = 1
        for rec in records:
            ok, payload = _extract_feature_row_safe(rec, label_lookup=label_lookup, role_lookup=role_lookup)
            if ok:
                rows.append(payload)
            else:
                errors.append(payload)

    if not rows:
        raise RuntimeError("no trajectory rows extracted")

    out_df = pd.DataFrame(rows)
    feature_cols = [
        "n_frames",
        "ligand_atom_count",
        "protein_res_count",
        "mean_min_distance_A",
        "min_min_distance_A",
        "final_min_distance_A",
        "contact_fraction_4p5A",
        "contact_fraction_6A",
        "contact_fraction_8A",
        "centroid_path_A",
        "mean_step_A",
        "max_step_A",
        "centroid_dispersion_A",
        "final_shift_A",
        "affinity_hint",
        "k_attr",
        "protein_repulse",
        "sim_fps",
    ]
    feature_matrix = out_df[feature_cols].fillna(0.0).to_numpy(dtype=np.float32, copy=True)
    labels = out_df["is_binder"].to_numpy(dtype=np.int8, copy=True)
    quality = out_df["quality_score"].to_numpy(dtype=np.float32, copy=True)
    targets = out_df["target"].astype(str).to_numpy(dtype=np.str_)
    ligand_ids = out_df["ligand_id"].astype(str).to_numpy(dtype=np.str_)
    roles = out_df["role"].astype(str).to_numpy(dtype=np.str_)
    queue_ids = out_df["queue_id"].astype(str).to_numpy(dtype=np.str_)

    out_csv = str(args.out_csv).strip()
    out_npz = str(args.out_npz).strip()
    out_json = str(args.out_json).strip()
    out_md = str(args.out_md).strip()
    _ensure_parent(out_csv)
    _ensure_parent(out_npz)
    _ensure_parent(out_json)
    _ensure_parent(out_md)

    out_df.to_csv(out_csv, index=False)
    np.savez(
        out_npz,
        feature_matrix=feature_matrix,
        feature_names=np.asarray(feature_cols, dtype=np.str_),
        labels=labels,
        quality_score=quality,
        targets=targets,
        ligand_ids=ligand_ids,
        roles=roles,
        queue_ids=queue_ids,
    )

    summary = {
        "ok": True,
        "rows_total": int(len(manifest_df)),
        "rows_emitted": int(len(out_df)),
        "rows_failed": int(len(errors)),
        "binder_rows": int(np.sum(labels >= 1)),
        "unknown_label_rows": int(np.sum(labels < 0)),
        "targets": int(out_df["target"].nunique()),
        "feature_dim": int(feature_matrix.shape[1]),
        "parallel_enabled": bool(parallel_enabled),
        "workers_used": int(workers_used),
        "parallel_threshold": int(parallel_threshold),
        "chunksize": int(chunksize),
        "artifacts": {
            "out_csv": out_csv,
            "out_npz": out_npz,
            "out_json": out_json,
            "out_md": out_md,
        },
        "feature_cols": feature_cols,
        "errors_preview": errors[:32],
    }
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(
            "\n".join(
                [
                    "# Ligand Trajectory Aux Dataset",
                    "",
                    f"- rows_total: {summary['rows_total']}",
                    f"- rows_emitted: {summary['rows_emitted']}",
                    f"- rows_failed: {summary['rows_failed']}",
                    f"- binder_rows: {summary['binder_rows']}",
                    f"- unknown_label_rows: {summary['unknown_label_rows']}",
                    f"- targets: {summary['targets']}",
                    f"- feature_dim: {summary['feature_dim']}",
                    f"- parallel_enabled: {summary['parallel_enabled']}",
                    f"- workers_used: {summary['workers_used']}",
                    f"- out_csv: `{out_csv}`",
                    f"- out_npz: `{out_npz}`",
                ]
            )
            + "\n"
        )
    return summary


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Extract auxiliary training features from ligand stage2 trajectory npz bundles."
    )
    p.add_argument("--stage2-manifest-csv", type=str, required=True)
    p.add_argument("--labels-csv", type=str, default="")
    p.add_argument("--split-csv", type=str, default="")
    p.add_argument("--max-rows", type=int, default=0)
    p.add_argument("--workers", type=int, default=0)
    p.add_argument("--parallel-threshold", type=int, default=128)
    p.add_argument("--chunksize", type=int, default=32)
    p.add_argument("--require-npz-only", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--out-csv", type=str, required=True)
    p.add_argument("--out-npz", type=str, required=True)
    p.add_argument("--out-json", type=str, required=True)
    p.add_argument("--out-md", type=str, required=True)
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    build_dataset(args)


if __name__ == "__main__":
    main()
