#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from core.definitions import ResearchConstants


def _safe_name(name: str) -> str:
    return "".join(ch if (ch.isalnum() or ch in ("-", "_")) else "_" for ch in str(name)).strip("_")


def _parse_targets(spec: str) -> List[str]:
    s = str(spec).strip().lower()
    if s == "all":
        return list(ResearchConstants.CHALLENGES.keys())
    out = [x.strip() for x in str(spec).split(",") if x.strip()]
    uniq: List[str] = []
    seen = set()
    for t in out:
        if t in seen:
            continue
        uniq.append(t)
        seen.add(t)
    return uniq


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return float(default)
        if isinstance(v, float) and (not np.isfinite(v)):
            return float(default)
        return float(v)
    except Exception:
        return float(default)


def _clip_by_quantile(x: np.ndarray, q_low: float, q_high: float) -> np.ndarray:
    vals = np.asarray(x, dtype=np.float64)
    if vals.size == 0:
        return vals
    lo = float(np.quantile(vals, float(q_low)))
    hi = float(np.quantile(vals, float(q_high)))
    if hi <= lo:
        hi = lo + 1e-6
    return np.clip(vals, lo, hi)


def _fd_bin_count(values: np.ndarray, min_bins: int, max_bins: int, fallback_bins: int) -> int:
    vals = np.asarray(values, dtype=np.float64)
    vals = vals[np.isfinite(vals)]
    if vals.size < 4:
        return int(max(min_bins, min(max_bins, fallback_bins)))
    q75 = float(np.quantile(vals, 0.75))
    q25 = float(np.quantile(vals, 0.25))
    iqr = max(q75 - q25, 1e-12)
    width = 2.0 * iqr * (vals.size ** (-1.0 / 3.0))
    data_range = max(float(vals.max() - vals.min()), 1e-12)
    if width <= 1e-12:
        bins = int(fallback_bins)
    else:
        bins = int(math.ceil(data_range / width))
    bins = max(int(min_bins), min(int(max_bins), int(bins)))
    return int(max(2, bins))


def _robust_aggregate(values: List[float], method: str, trim_fraction: float) -> Tuple[float, float]:
    vals = np.asarray([float(v) for v in values if np.isfinite(float(v))], dtype=np.float64)
    if vals.size == 0:
        return float("nan"), 0.0
    m = str(method).strip().lower()
    if m == "median":
        return float(np.median(vals)), 0.0
    if m == "trimmed":
        n = int(vals.size)
        k = int(math.floor(max(0.0, min(0.45, float(trim_fraction))) * n))
        if (n - 2 * k) <= 0:
            return float(np.mean(vals)), 0.0
        s = np.sort(vals)
        kept = s[k : n - k]
        outlier_rate = float((n - kept.size) / max(n, 1))
        return float(np.mean(kept)), outlier_rate
    return float(np.mean(vals)), 0.0


def _split_ref_pred_indices(
    n_frames: int,
    *,
    split_mode: str,
    split_window_frames: int,
    split_window_stride: int,
    replica_index: int,
) -> Tuple[np.ndarray, np.ndarray]:
    n = int(n_frames)
    if n <= 0:
        return np.zeros((0,), dtype=np.int64), np.zeros((0,), dtype=np.int64)
    mode = str(split_mode).strip().lower()
    if mode == "half":
        cut = max(2, n // 2)
        ref_idx = np.arange(0, cut, dtype=np.int64)
        pred_idx = np.arange(cut, n, dtype=np.int64)
        if pred_idx.size < 2:
            pred_idx = np.arange(max(0, cut - 2), n, dtype=np.int64)
        return ref_idx, pred_idx

    # window_stratified: alternating contiguous windows across trajectory time.
    w = max(2, int(split_window_frames))
    stride = max(1, int(split_window_stride))
    if w >= n:
        ref_idx = np.arange(0, n, 2, dtype=np.int64)
        pred_idx = np.arange(1, n, 2, dtype=np.int64)
        if pred_idx.size == 0:
            pred_idx = np.arange(max(0, n - 2), n, dtype=np.int64)
        return ref_idx, pred_idx

    windows: List[np.ndarray] = []
    start = 0
    while start + w <= n:
        windows.append(np.arange(start, start + w, dtype=np.int64))
        start += stride
    if not windows:
        windows = [np.arange(0, n, dtype=np.int64)]

    ref_parts: List[np.ndarray] = []
    pred_parts: List[np.ndarray] = []
    for i, idx in enumerate(windows):
        parity = (i + int(replica_index)) % 2
        if parity == 0:
            ref_parts.append(idx)
        else:
            pred_parts.append(idx)

    if len(ref_parts) == 0 or len(pred_parts) == 0:
        ref_idx = np.arange(0, n, 2, dtype=np.int64)
        pred_idx = np.arange(1, n, 2, dtype=np.int64)
    else:
        ref_idx = np.unique(np.concatenate(ref_parts))
        pred_idx = np.unique(np.concatenate(pred_parts))

    if pred_idx.size == 0:
        pred_idx = np.arange(max(0, n - 2), n, dtype=np.int64)
    if ref_idx.size == 0:
        ref_idx = np.arange(0, min(2, n), dtype=np.int64)
    return ref_idx.astype(np.int64), pred_idx.astype(np.int64)


def _kabsch_align_rmsd(x: np.ndarray, y: np.ndarray) -> float:
    x0 = np.asarray(x, dtype=np.float64)
    y0 = np.asarray(y, dtype=np.float64)
    x0 = x0 - x0.mean(axis=0, keepdims=True)
    y0 = y0 - y0.mean(axis=0, keepdims=True)
    cov = x0.T @ y0
    u, _s, vh = np.linalg.svd(cov, full_matrices=False)
    d = np.linalg.det(u @ vh)
    if d < 0.0:
        u[:, -1] *= -1.0
    r = u @ vh
    xa = x0 @ r
    diff = xa - y0
    return float(np.sqrt(np.mean(np.sum(diff * diff, axis=1))))


def _radius_of_gyration(coords: np.ndarray) -> float:
    c = np.asarray(coords, dtype=np.float64)
    center = c.mean(axis=0, keepdims=True)
    d2 = np.sum((c - center) ** 2, axis=1)
    return float(np.sqrt(np.mean(d2)))


def _autocorr_1d(x: np.ndarray, max_lag: int) -> np.ndarray:
    vals = np.asarray(x, dtype=np.float64)
    if vals.size < 2:
        return np.ones(1, dtype=np.float64)
    vals = vals - np.mean(vals)
    var = float(np.var(vals))
    if var <= 1e-16:
        return np.ones(min(max_lag + 1, vals.size), dtype=np.float64)
    lags = min(int(max_lag), vals.size - 1)
    out = np.empty(lags + 1, dtype=np.float64)
    out[0] = 1.0
    n = vals.size
    for lag in range(1, lags + 1):
        out[lag] = float(np.dot(vals[:-lag], vals[lag:]) / ((n - lag) * var))
    return out


def _integrated_timescale(x: np.ndarray, max_lag: int) -> float:
    ac = _autocorr_1d(x, max_lag=max_lag)
    if ac.size <= 1:
        return 1.0
    pos = ac[1:]
    pos = pos[pos > 0.0]
    if pos.size == 0:
        return 1.0
    return float(1.0 + 2.0 * np.sum(pos))


def _corr_crossing_time(x: np.ndarray, max_lag: int, threshold: float = 1.0 / math.e) -> float:
    ac = _autocorr_1d(x, max_lag=max_lag)
    for i in range(1, ac.size):
        if ac[i] <= threshold:
            return float(i)
    return float(max(1, ac.size - 1))


def _hist_pmf(v: np.ndarray, bins: int, vmin: float, vmax: float, eps: float = 1e-12) -> Tuple[np.ndarray, np.ndarray]:
    h, e = np.histogram(v, bins=int(bins), range=(float(vmin), float(vmax)), density=False)
    p = h.astype(np.float64) + float(eps)
    p /= np.sum(p)
    f = -np.log(p)
    f -= np.min(f)
    return p, f


def _jsd(p: np.ndarray, q: np.ndarray, eps: float = 1e-12) -> float:
    p = np.asarray(p, dtype=np.float64) + float(eps)
    q = np.asarray(q, dtype=np.float64) + float(eps)
    p = p / np.sum(p)
    q = q / np.sum(q)
    m = 0.5 * (p + q)
    kl_pm = np.sum(p * np.log(p / m))
    kl_qm = np.sum(q * np.log(q / m))
    return float(0.5 * (kl_pm + kl_qm))


def _emd_1d(p: np.ndarray, q: np.ndarray) -> float:
    p = np.asarray(p, dtype=np.float64)
    q = np.asarray(q, dtype=np.float64)
    p = p / max(np.sum(p), 1e-12)
    q = q / max(np.sum(q), 1e-12)
    cp = np.cumsum(p)
    cq = np.cumsum(q)
    return float(np.mean(np.abs(cp - cq)))


def _pairwise_distances(coords: np.ndarray) -> np.ndarray:
    x = np.asarray(coords, dtype=np.float64)
    diff = x[:, None, :] - x[None, :, :]
    d = np.sqrt(np.sum(diff * diff, axis=-1))
    return d


def _contact_prob(traj: np.ndarray, cutoff: float) -> np.ndarray:
    t, n, _ = traj.shape
    acc = np.zeros((n, n), dtype=np.float64)
    for i in range(t):
        d = _pairwise_distances(traj[i])
        acc += (d <= float(cutoff)).astype(np.float64)
    acc /= float(max(t, 1))
    return acc


def _upper_triangle_flat(m: np.ndarray, min_sep: int = 3) -> np.ndarray:
    n = int(m.shape[0])
    rows = []
    cols = []
    for i in range(n):
        j0 = i + max(1, int(min_sep))
        if j0 >= n:
            continue
        for j in range(j0, n):
            rows.append(i)
            cols.append(j)
    if not rows:
        return np.zeros(0, dtype=np.float64)
    return m[np.asarray(rows, dtype=np.int64), np.asarray(cols, dtype=np.int64)]


def _saxs_profile_from_coords(coords: np.ndarray, q_values: np.ndarray) -> np.ndarray:
    d = _pairwise_distances(coords)
    n = d.shape[0]
    tri_i, tri_j = np.triu_indices(n, k=1)
    rij = d[tri_i, tri_j]
    out = np.zeros_like(q_values, dtype=np.float64)
    for k, q in enumerate(q_values):
        qr = q * rij
        sinc = np.where(np.abs(qr) < 1e-9, 1.0, np.sin(qr) / qr)
        out[k] = float(np.sum(sinc))
    # add self terms
    out += float(n)
    return out


def _saxs_chi2(pred: np.ndarray, ref: np.ndarray, eps: float = 1e-9) -> float:
    p = np.asarray(pred, dtype=np.float64)
    r = np.asarray(ref, dtype=np.float64)
    scale = float(np.dot(p, r) / max(np.dot(p, p), eps))
    denom = np.maximum(np.abs(r), eps)
    return float(np.mean(((scale * p - r) / denom) ** 2))


def _load_trajectory(path: str) -> np.ndarray:
    arr = np.load(path)
    if isinstance(arr, np.lib.npyio.NpzFile):
        keys = ["trajectory", "coords", "frames", "ligand_frames", "protein_ca"]
        found_key = next((key for key in keys if key in arr.files), "")
        if not found_key:
            raise ValueError(f"npz trajectory has no supported coordinate key: {arr.files} ({path})")
        a = np.asarray(arr[found_key])
    else:
        a = np.asarray(arr)
    if a.ndim == 2:
        if a.shape[1] != 3 and a.shape[0] == 3:
            a = a.T
        if a.shape[1] != 3:
            raise ValueError(f"invalid coordinates shape: {a.shape} ({path})")
        a = a[None, :, :]
    if a.ndim != 3 or a.shape[2] != 3:
        raise ValueError(f"trajectory must be [T,N,3], got {a.shape} ({path})")
    return a.astype(np.float64, copy=False)


def _project_ca_if_needed(traj: np.ndarray, beads_per_residue: Optional[float], bead_order: str) -> np.ndarray:
    bpr = float(beads_per_residue) if beads_per_residue is not None else 1.0
    if bpr < 1.5:
        return traj
    n_atoms = int(traj.shape[1])
    if n_atoms % 2 != 0:
        return traj
    if str(bead_order).strip().lower() == "interleaved_ca_sc":
        return traj[:, 0::2, :]
    return traj[:, : n_atoms // 2, :]


def _estimate_metrics_for_target(
    traj: np.ndarray,
    *,
    min_frames: int,
    rmsd_bins: int,
    min_rmsd_bins: int,
    max_rmsd_bins: int,
    adaptive_rmsd_bins: bool,
    split_mode: str,
    split_replicas: int,
    split_window_frames: int,
    split_window_stride: int,
    min_effective_frames: int,
    thermo_agg_method: str,
    kinetics_agg_method: str,
    experiment_agg_method: str,
    trim_fraction: float,
    pmf_pseudocount: float,
    tail_clip_low: float,
    tail_clip_high: float,
    kinetics_min_signal_std: float,
    kinetics_min_denom_eps: float,
    temperature_k: float,
    k_boltzmann_kcal_per_mol_k: float,
    contact_cutoff: float,
    noe_contact_cutoff: float,
    noe_tol_frac: float,
    saxs_q_min: float,
    saxs_q_max: float,
    saxs_q_bins: int,
) -> Dict[str, Any]:
    if traj.shape[0] < int(min_frames):
        raise ValueError(f"not enough frames: {traj.shape[0]} < {min_frames}")

    t = int(traj.shape[0])
    rep_count = max(1, int(split_replicas))
    min_eff = max(2, int(min_effective_frames))
    replicate_rows: List[Dict[str, float]] = []
    split_stats: List[Dict[str, int]] = []
    failed_replicates = 0

    for rep in range(rep_count):
        ref_idx, pred_idx = _split_ref_pred_indices(
            n_frames=t,
            split_mode=split_mode,
            split_window_frames=int(split_window_frames),
            split_window_stride=int(split_window_stride),
            replica_index=rep,
        )
        if (ref_idx.size < min_eff) or (pred_idx.size < min_eff):
            failed_replicates += 1
            continue

        ref = traj[ref_idx]
        pred = traj[pred_idx]
        split_stats.append({"replica": int(rep), "ref_frames": int(ref.shape[0]), "pred_frames": int(pred.shape[0])})

        native = ref[0]
        ref_rmsd = np.asarray([_kabsch_align_rmsd(f, native) for f in ref], dtype=np.float64)
        pred_rmsd = np.asarray([_kabsch_align_rmsd(f, native) for f in pred], dtype=np.float64)
        ref_rg = np.asarray([_radius_of_gyration(f) for f in ref], dtype=np.float64)
        pred_rg = np.asarray([_radius_of_gyration(f) for f in pred], dtype=np.float64)

        if (ref_rmsd.size < 3) or (pred_rmsd.size < 3):
            failed_replicates += 1
            continue

        max_lag = max(2, min(100, ref_rmsd.size - 1, pred_rmsd.size - 1))
        if (np.std(ref_rmsd) < float(kinetics_min_signal_std)) and (np.std(pred_rmsd) < float(kinetics_min_signal_std)):
            mfpt_ref = 1.0
            mfpt_pred = 1.0
        else:
            mfpt_ref = _corr_crossing_time(ref_rmsd, max_lag=max_lag)
            mfpt_pred = _corr_crossing_time(pred_rmsd, max_lag=max_lag)

        if (np.std(ref_rg) < float(kinetics_min_signal_std)) and (np.std(pred_rg) < float(kinetics_min_signal_std)):
            its_ref = 1.0
            its_pred = 1.0
        else:
            its_ref = _integrated_timescale(ref_rg, max_lag=max_lag)
            its_pred = _integrated_timescale(pred_rg, max_lag=max_lag)

        ref_rmsd_c = _clip_by_quantile(ref_rmsd, q_low=float(tail_clip_low), q_high=float(tail_clip_high))
        pred_rmsd_c = _clip_by_quantile(pred_rmsd, q_low=float(tail_clip_low), q_high=float(tail_clip_high))
        all_rmsd = np.concatenate([ref_rmsd_c, pred_rmsd_c], axis=0)
        rmsd_min = float(np.min(all_rmsd))
        rmsd_max = float(np.max(all_rmsd))
        if abs(rmsd_max - rmsd_min) < 1e-9:
            rmsd_max = rmsd_min + 1.0
        if bool(adaptive_rmsd_bins):
            bins = _fd_bin_count(all_rmsd, min_bins=int(min_rmsd_bins), max_bins=int(max_rmsd_bins), fallback_bins=int(rmsd_bins))
        else:
            bins = int(max(2, rmsd_bins))
        p_ref_rmsd, f_ref_rmsd = _hist_pmf(
            ref_rmsd_c,
            bins=bins,
            vmin=rmsd_min,
            vmax=rmsd_max,
            eps=float(max(pmf_pseudocount, 1e-15)),
        )
        p_pred_rmsd, f_pred_rmsd = _hist_pmf(
            pred_rmsd_c,
            bins=bins,
            vmin=rmsd_min,
            vmax=rmsd_max,
            eps=float(max(pmf_pseudocount, 1e-15)),
        )
        delta_g_rmse_kT = float(np.sqrt(np.mean((f_ref_rmsd - f_pred_rmsd) ** 2)))
        kbt_kcal = float(max(1e-12, float(temperature_k) * float(k_boltzmann_kcal_per_mol_k)))
        delta_g_rmse = float(delta_g_rmse_kT * kbt_kcal)

        # Combined support state boundaries (not ref-only).
        q1 = float(np.quantile(all_rmsd, 0.33))
        q2 = float(np.quantile(all_rmsd, 0.66))

        def _state_hist(x: np.ndarray) -> np.ndarray:
            s0 = np.sum(x <= q1)
            s1 = np.sum((x > q1) & (x <= q2))
            s2 = np.sum(x > q2)
            out = np.asarray([s0, s1, s2], dtype=np.float64)
            out /= max(np.sum(out), 1.0)
            return out

        state_jsd = _jsd(_state_hist(ref_rmsd_c), _state_hist(pred_rmsd_c), eps=float(max(pmf_pseudocount, 1e-15)))
        pmf_emd = _emd_1d(p_ref_rmsd, p_pred_rmsd)

        # Pseudo NOE: derive constraints from reference-native close contacts.
        d_native = _pairwise_distances(native)
        n = d_native.shape[0]
        pair_i = []
        pair_j = []
        upper = float(noe_contact_cutoff)
        for i in range(n):
            for j in range(i + 3, n):
                if d_native[i, j] <= upper:
                    pair_i.append(i)
                    pair_j.append(j)
        if pair_i:
            pi = np.asarray(pair_i, dtype=np.int64)
            pj = np.asarray(pair_j, dtype=np.int64)
            ref_d0 = d_native[pi, pj]
            max_allow = ref_d0 * (1.0 + float(noe_tol_frac))
            pred_viol = 0
            total = int(pred.shape[0]) * int(pi.size)
            for f in pred:
                d = _pairwise_distances(f)
                pred_viol += int(np.sum(d[pi, pj] > max_allow))
            nmr_noe_violation_rate = float(pred_viol / max(total, 1))
        else:
            nmr_noe_violation_rate = 0.0

        # CryoEM proxy: contact-prob map correlation between splits.
        cp_ref = _contact_prob(ref, cutoff=float(contact_cutoff))
        cp_pred = _contact_prob(pred, cutoff=float(contact_cutoff))
        v_ref = _upper_triangle_flat(cp_ref, min_sep=3)
        v_pred = _upper_triangle_flat(cp_pred, min_sep=3)
        if v_ref.size == 0:
            cryoem_map_cc = 1.0
        else:
            vr = v_ref - np.mean(v_ref)
            vp = v_pred - np.mean(v_pred)
            denom = float(np.sqrt(np.dot(vr, vr) * np.dot(vp, vp)))
            cryoem_map_cc = float(np.dot(vr, vp) / denom) if denom > 1e-12 else 1.0

        # SAXS proxy: compare split-average Debye profile.
        q = np.linspace(float(saxs_q_min), float(saxs_q_max), int(max(saxs_q_bins, 4)), dtype=np.float64)
        i_ref = np.zeros_like(q)
        i_pred = np.zeros_like(q)
        for f in ref:
            i_ref += _saxs_profile_from_coords(f, q)
        for f in pred:
            i_pred += _saxs_profile_from_coords(f, q)
        i_ref /= max(ref.shape[0], 1)
        i_pred /= max(pred.shape[0], 1)
        saxs_chi2 = _saxs_chi2(i_pred, i_ref, eps=float(max(kinetics_min_denom_eps, 1e-12)))

        replicate_rows.append(
            {
                "mfpt_pred": float(mfpt_pred),
                "mfpt_ref": float(max(mfpt_ref, float(kinetics_min_denom_eps))),
                "its_pred": float(its_pred),
                "its_ref": float(max(its_ref, float(kinetics_min_denom_eps))),
                "deltaG_rmse_kcal_mol": float(delta_g_rmse),
                "deltaG_rmse_kT": float(delta_g_rmse_kT),
                "state_population_jsd": float(state_jsd),
                "pmf_1d_emd": float(pmf_emd),
                "nmr_noe_violation_rate": float(nmr_noe_violation_rate),
                "cryoem_map_cc": float(cryoem_map_cc),
                "saxs_chi2": float(saxs_chi2),
                "rmsd_bins_used": float(bins),
                "ref_frames": float(ref.shape[0]),
                "pred_frames": float(pred.shape[0]),
            }
        )

    if len(replicate_rows) == 0:
        raise ValueError("no valid split replicas after effective-frame filtering")

    rep_df = pd.DataFrame(replicate_rows)
    thermo_outlier_rates: Dict[str, float] = {}
    kinetics_outlier_rates: Dict[str, float] = {}
    experiment_outlier_rates: Dict[str, float] = {}
    metrics: Dict[str, float] = {}

    thermo_keys = ["deltaG_rmse_kcal_mol", "state_population_jsd", "pmf_1d_emd"]
    kinetics_keys = ["mfpt_pred", "mfpt_ref", "its_pred", "its_ref"]
    experiment_keys = ["nmr_noe_violation_rate", "cryoem_map_cc", "saxs_chi2"]
    for key in thermo_keys:
        v, r = _robust_aggregate(rep_df[key].tolist(), method=thermo_agg_method, trim_fraction=trim_fraction)
        metrics[key] = float(v)
        thermo_outlier_rates[key] = float(r)
    for key in kinetics_keys:
        v, r = _robust_aggregate(rep_df[key].tolist(), method=kinetics_agg_method, trim_fraction=trim_fraction)
        metrics[key] = float(max(v, float(kinetics_min_denom_eps) if key.endswith("_ref") else v))
        kinetics_outlier_rates[key] = float(r)
    for key in experiment_keys:
        v, r = _robust_aggregate(rep_df[key].tolist(), method=experiment_agg_method, trim_fraction=trim_fraction)
        metrics[key] = float(v)
        experiment_outlier_rates[key] = float(r)

    diag = {
        "split_mode": str(split_mode),
        "split_replicas_requested": int(rep_count),
        "split_replicas_used": int(len(replicate_rows)),
        "split_replicas_failed": int(failed_replicates),
        "effective_ref_frames_mean": float(rep_df["ref_frames"].mean()),
        "effective_pred_frames_mean": float(rep_df["pred_frames"].mean()),
        "effective_ref_frames_min": int(rep_df["ref_frames"].min()),
        "effective_pred_frames_min": int(rep_df["pred_frames"].min()),
        "rmsd_bins_mean": float(rep_df["rmsd_bins_used"].mean()),
        "thermo_outlier_rate_mean": float(np.mean(list(thermo_outlier_rates.values()))) if thermo_outlier_rates else 0.0,
        "kinetics_outlier_rate_mean": float(np.mean(list(kinetics_outlier_rates.values()))) if kinetics_outlier_rates else 0.0,
        "split_stats": split_stats,
        "temperature_k": float(temperature_k),
        "k_boltzmann_kcal_per_mol_k": float(k_boltzmann_kcal_per_mol_k),
        "kbt_kcal_mol": float(max(1e-12, float(temperature_k) * float(k_boltzmann_kcal_per_mol_k))),
    }
    metrics["diagnostics"] = diag  # type: ignore[index]
    metrics["replicate_rows"] = rep_df.to_dict(orient="records")  # type: ignore[index]
    return metrics


def run_build(args: argparse.Namespace) -> Dict[str, Any]:
    manifest = pd.read_csv(str(args.manifest_csv))
    if manifest.empty:
        raise ValueError(f"manifest is empty: {args.manifest_csv}")

    targets = _parse_targets(str(args.targets))
    target_set = set(targets)
    rows = manifest[manifest["target"].astype(str).isin(target_set)].copy()
    if rows.empty:
        raise ValueError("no manifest rows matched requested targets")

    kinetics_rows: List[Dict[str, Any]] = []
    thermo_rows: List[Dict[str, Any]] = []
    experiment_rows: List[Dict[str, Any]] = []
    per_target: List[Dict[str, Any]] = []
    diagnostics_rows: List[Dict[str, Any]] = []
    failed: List[Dict[str, Any]] = []

    for _, row in rows.iterrows():
        target = str(row.get("target", "")).strip()
        path = str(row.get("path", "")).strip()
        if not path:
            path = str(row.get("trajectory_npz", "")).strip()
        if not path:
            path = str(row.get("trajectory_npy", "")).strip()
        if not path:
            path = str(row.get("trajectory_path", "")).strip()
        if not target or not path:
            continue
        try:
            traj = _load_trajectory(path)
            traj = _project_ca_if_needed(
                traj,
                beads_per_residue=row.get("beads_per_residue"),
                bead_order=str(row.get("bead_order", "ca_then_sc")),
            )
            metrics = _estimate_metrics_for_target(
                traj,
                min_frames=int(args.min_frames),
                rmsd_bins=int(args.rmsd_bins),
                min_rmsd_bins=int(args.min_rmsd_bins),
                max_rmsd_bins=int(args.max_rmsd_bins),
                adaptive_rmsd_bins=bool(args.adaptive_rmsd_bins),
                split_mode=str(args.split_mode),
                split_replicas=int(args.split_replicas),
                split_window_frames=int(args.split_window_frames),
                split_window_stride=int(args.split_window_stride),
                min_effective_frames=int(args.min_effective_frames),
                thermo_agg_method=str(args.thermo_agg_method),
                kinetics_agg_method=str(args.kinetics_agg_method),
                experiment_agg_method=str(args.experiment_agg_method),
                trim_fraction=float(args.trim_fraction),
                pmf_pseudocount=float(args.pmf_pseudocount),
                tail_clip_low=float(args.tail_clip_low),
                tail_clip_high=float(args.tail_clip_high),
                kinetics_min_signal_std=float(args.kinetics_min_signal_std),
                kinetics_min_denom_eps=float(args.kinetics_min_denom_eps),
                temperature_k=float(args.temperature_k),
                k_boltzmann_kcal_per_mol_k=float(args.k_boltzmann_kcal_per_mol_k),
                contact_cutoff=float(args.contact_cutoff),
                noe_contact_cutoff=float(args.noe_contact_cutoff),
                noe_tol_frac=float(args.noe_tolerance_frac),
                saxs_q_min=float(args.saxs_q_min),
                saxs_q_max=float(args.saxs_q_max),
                saxs_q_bins=int(args.saxs_q_bins),
            )
            diagnostics = metrics.pop("diagnostics", {}) if isinstance(metrics.get("diagnostics"), dict) else {}
            _ = metrics.pop("replicate_rows", None)
            kinetics_rows.append(
                {
                    "target": target,
                    "mfpt_pred": metrics["mfpt_pred"],
                    "mfpt_ref": metrics["mfpt_ref"],
                    "its_pred": metrics["its_pred"],
                    "its_ref": metrics["its_ref"],
                    "source": "openmm_2bead_split_self_consistency",
                    "notes": f"manifest_path={path}",
                }
            )
            thermo_rows.append(
                {
                    "target": target,
                    "deltaG_rmse_kcal_mol": metrics["deltaG_rmse_kcal_mol"],
                    "state_population_jsd": metrics["state_population_jsd"],
                    "pmf_1d_emd": metrics["pmf_1d_emd"],
                    "source": "openmm_2bead_split_self_consistency",
                    "notes": f"manifest_path={path}",
                }
            )
            experiment_rows.append(
                {
                    "target": target,
                    "nmr_noe_violation_rate": metrics["nmr_noe_violation_rate"],
                    "cryoem_map_cc": metrics["cryoem_map_cc"],
                    "saxs_chi2": metrics["saxs_chi2"],
                    "source": "openmm_2bead_split_self_consistency",
                    "notes": f"manifest_path={path}",
                }
            )
            per_target.append({"target": target, "path": path, **metrics})
            diagnostics_rows.append(
                {
                    "target": target,
                    "path": path,
                    "split_mode": diagnostics.get("split_mode"),
                    "split_replicas_requested": diagnostics.get("split_replicas_requested"),
                    "split_replicas_used": diagnostics.get("split_replicas_used"),
                    "split_replicas_failed": diagnostics.get("split_replicas_failed"),
                    "effective_ref_frames_mean": diagnostics.get("effective_ref_frames_mean"),
                    "effective_pred_frames_mean": diagnostics.get("effective_pred_frames_mean"),
                    "effective_ref_frames_min": diagnostics.get("effective_ref_frames_min"),
                    "effective_pred_frames_min": diagnostics.get("effective_pred_frames_min"),
                    "rmsd_bins_mean": diagnostics.get("rmsd_bins_mean"),
                    "thermo_outlier_rate_mean": diagnostics.get("thermo_outlier_rate_mean"),
                    "kinetics_outlier_rate_mean": diagnostics.get("kinetics_outlier_rate_mean"),
                }
            )
        except Exception as exc:
            failed.append({"target": target, "path": path, "error": f"{type(exc).__name__}: {exc}"})

    kinetics_df = pd.DataFrame(kinetics_rows).sort_values("target")
    thermo_df = pd.DataFrame(thermo_rows).sort_values("target")
    experiment_df = pd.DataFrame(experiment_rows).sort_values("target")

    os.makedirs(os.path.dirname(str(args.out_kinetics_csv)) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(str(args.out_thermo_csv)) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(str(args.out_experiment_csv)) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(str(args.out_diagnostics_csv)) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(str(args.out_diagnostics_json)) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(str(args.out_json)) or ".", exist_ok=True)
    kinetics_df.to_csv(str(args.out_kinetics_csv), index=False)
    thermo_df.to_csv(str(args.out_thermo_csv), index=False)
    experiment_df.to_csv(str(args.out_experiment_csv), index=False)
    diagnostics_df = pd.DataFrame(diagnostics_rows).sort_values("target") if diagnostics_rows else pd.DataFrame()
    diagnostics_df.to_csv(str(args.out_diagnostics_csv), index=False)
    diagnostics_payload = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "summary": {
            "targets_requested": int(len(targets)),
            "targets_with_diagnostics": int(len(diagnostics_rows)),
            "targets_failed": int(len(failed)),
            "split_mode": str(args.split_mode),
            "split_replicas": int(args.split_replicas),
        },
        "rows": diagnostics_rows,
        "failed_targets": failed,
    }
    with open(str(args.out_diagnostics_json), "w", encoding="utf-8") as f:
        json.dump(diagnostics_payload, f, indent=2, ensure_ascii=False)

    summary = {
        "targets_requested": int(len(targets)),
        "targets_built": int(len(per_target)),
        "targets_failed": int(len(failed)),
    }
    payload = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "inputs": {
            "manifest_csv": str(args.manifest_csv),
            "targets": targets,
            "min_frames": int(args.min_frames),
            "rmsd_bins": int(args.rmsd_bins),
            "adaptive_rmsd_bins": bool(args.adaptive_rmsd_bins),
            "min_rmsd_bins": int(args.min_rmsd_bins),
            "max_rmsd_bins": int(args.max_rmsd_bins),
            "split_mode": str(args.split_mode),
            "split_replicas": int(args.split_replicas),
            "split_window_frames": int(args.split_window_frames),
            "split_window_stride": int(args.split_window_stride),
            "min_effective_frames": int(args.min_effective_frames),
            "thermo_agg_method": str(args.thermo_agg_method),
            "kinetics_agg_method": str(args.kinetics_agg_method),
            "experiment_agg_method": str(args.experiment_agg_method),
            "trim_fraction": float(args.trim_fraction),
            "tail_clip_low": float(args.tail_clip_low),
            "tail_clip_high": float(args.tail_clip_high),
            "pmf_pseudocount": float(args.pmf_pseudocount),
            "kinetics_min_signal_std": float(args.kinetics_min_signal_std),
            "kinetics_min_denom_eps": float(args.kinetics_min_denom_eps),
            "temperature_k": float(args.temperature_k),
            "k_boltzmann_kcal_per_mol_k": float(args.k_boltzmann_kcal_per_mol_k),
            "contact_cutoff": float(args.contact_cutoff),
            "noe_contact_cutoff": float(args.noe_contact_cutoff),
            "noe_tolerance_frac": float(args.noe_tolerance_frac),
            "saxs_q_min": float(args.saxs_q_min),
            "saxs_q_max": float(args.saxs_q_max),
            "saxs_q_bins": int(args.saxs_q_bins),
        },
        "summary": summary,
        "artifacts": {
            "kinetics_csv": str(args.out_kinetics_csv),
            "thermo_csv": str(args.out_thermo_csv),
            "experiment_csv": str(args.out_experiment_csv),
            "diagnostics_csv": str(args.out_diagnostics_csv),
            "diagnostics_json": str(args.out_diagnostics_json),
        },
        "per_target_metrics": per_target,
        "diagnostics_rows": diagnostics_rows,
        "failed_targets": failed,
    }
    with open(str(args.out_json), "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return payload


def build_parser() -> argparse.ArgumentParser:
    stamp = dt.date.today().isoformat()
    p = argparse.ArgumentParser(
        description=(
            "Build kinetics/thermo/experiment claim input CSVs from OpenMM 2-bead trajectory manifest "
            "using split-half self-consistency metrics."
        )
    )
    p.add_argument("--manifest-csv", type=str, required=True)
    p.add_argument("--targets", type=str, default="all")
    p.add_argument("--min-frames", type=int, default=20)
    p.add_argument("--rmsd-bins", type=int, default=32)
    p.add_argument("--adaptive-rmsd-bins", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--min-rmsd-bins", type=int, default=12)
    p.add_argument("--max-rmsd-bins", type=int, default=80)
    p.add_argument("--split-mode", type=str, choices=["window_stratified", "half"], default="window_stratified")
    p.add_argument("--split-replicas", type=int, default=5)
    p.add_argument("--split-window-frames", type=int, default=24)
    p.add_argument("--split-window-stride", type=int, default=12)
    p.add_argument("--min-effective-frames", type=int, default=8)
    p.add_argument("--thermo-agg-method", type=str, choices=["mean", "median", "trimmed"], default="median")
    p.add_argument("--kinetics-agg-method", type=str, choices=["mean", "median", "trimmed"], default="median")
    p.add_argument("--experiment-agg-method", type=str, choices=["mean", "median", "trimmed"], default="median")
    p.add_argument("--trim-fraction", type=float, default=0.10)
    p.add_argument("--tail-clip-low", type=float, default=0.01)
    p.add_argument("--tail-clip-high", type=float, default=0.99)
    p.add_argument("--pmf-pseudocount", type=float, default=1.0)
    p.add_argument("--kinetics-min-signal-std", type=float, default=1e-6)
    p.add_argument("--kinetics-min-denom-eps", type=float, default=1e-12)
    p.add_argument("--temperature-k", type=float, default=300.0)
    p.add_argument("--k-boltzmann-kcal-per-mol-k", type=float, default=0.0019872041)
    p.add_argument("--contact-cutoff", type=float, default=1.2)
    p.add_argument("--noe-contact-cutoff", type=float, default=0.9)
    p.add_argument("--noe-tolerance-frac", type=float, default=0.2)
    p.add_argument("--saxs-q-min", type=float, default=0.1)
    p.add_argument("--saxs-q-max", type=float, default=3.0)
    p.add_argument("--saxs-q-bins", type=int, default=24)
    p.add_argument("--out-kinetics-csv", type=str, default=f"runs/kinetics_equivalence_input_real_openmm_{stamp}.csv")
    p.add_argument("--out-thermo-csv", type=str, default=f"runs/thermo_equivalence_input_real_openmm_{stamp}.csv")
    p.add_argument(
        "--out-experiment-csv",
        type=str,
        default=f"runs/experiment_consistency_input_real_openmm_{stamp}.csv",
    )
    p.add_argument("--out-diagnostics-csv", type=str, default=f"runs/claim_input_diagnostics_{stamp}.csv")
    p.add_argument("--out-diagnostics-json", type=str, default=f"runs/claim_input_diagnostics_{stamp}.json")
    p.add_argument("--out-json", type=str, default=f"runs/claim_input_real_openmm_summary_{stamp}.json")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = run_build(args)
    print(json.dumps(payload.get("summary", {}), indent=2, ensure_ascii=False))
    print(f"Wrote kinetics CSV: {args.out_kinetics_csv}")
    print(f"Wrote thermo CSV: {args.out_thermo_csv}")
    print(f"Wrote experiment CSV: {args.out_experiment_csv}")
    print(f"Wrote diagnostics CSV: {args.out_diagnostics_csv}")
    print(f"Wrote diagnostics JSON: {args.out_diagnostics_json}")
    print(f"Wrote JSON: {args.out_json}")


if __name__ == "__main__":
    main()
