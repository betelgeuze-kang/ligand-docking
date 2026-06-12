#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

try:
    import pydssp as _pydssp  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    _pydssp = None


@dataclass
class AtomRecord:
    record_name: str
    serial: int
    atom_name: str
    alt_loc: str
    res_name: str
    chain_id: str
    res_seq: int
    i_code: str
    occupancy: float
    element: str
    charge: str


@dataclass
class PdbFrame:
    path: str
    target: str
    sample_idx: int
    step: int
    atoms: List[AtomRecord]
    coords: np.ndarray
    headers: List[str]
    ters: List[str]
    conects: List[str]


def _safe_int(text: str, default: int = 0) -> int:
    try:
        return int(str(text).strip())
    except Exception:
        return int(default)


def _safe_float(text: str, default: float = 0.0) -> float:
    try:
        return float(str(text).strip())
    except Exception:
        return float(default)


def _slug(text: str) -> str:
    tok = str(text).strip().lower()
    tok = re.sub(r"[^a-z0-9]+", "_", tok)
    tok = re.sub(r"_+", "_", tok).strip("_")
    return tok or "target"


def _collect_inputs(paths: Sequence[str], globs: Sequence[str]) -> List[str]:
    out: List[str] = []
    for p in paths:
        t = str(p).strip()
        if t:
            out.append(t)
    for g in globs:
        tok = str(g).strip()
        if not tok:
            continue
        import glob

        out.extend(sorted(glob.glob(tok)))
    uniq: List[str] = []
    seen = set()
    for p in out:
        ap = os.path.abspath(str(p))
        if ap in seen:
            continue
        seen.add(ap)
        if os.path.isfile(ap):
            uniq.append(ap)
    return uniq


def _parse_atom_line(line: str) -> Tuple[AtomRecord, np.ndarray]:
    rec = str(line[:6]).strip() or "ATOM"
    serial = _safe_int(line[6:11], 0)
    atom_name = str(line[12:16]).strip() or "CA"
    alt_loc = str(line[16:17]).strip()
    res_name = str(line[17:20]).strip() or "GLY"
    chain_id = str(line[21:22]).strip() or "A"
    res_seq = _safe_int(line[22:26], 1)
    i_code = str(line[26:27]).strip()
    x = _safe_float(line[30:38], 0.0)
    y = _safe_float(line[38:46], 0.0)
    z = _safe_float(line[46:54], 0.0)
    occ = _safe_float(line[54:60], 1.0)
    element = str(line[76:78]).strip() or atom_name[:1]
    charge = str(line[78:80]).strip()
    atom = AtomRecord(
        record_name=rec,
        serial=int(serial),
        atom_name=str(atom_name),
        alt_loc=str(alt_loc),
        res_name=str(res_name),
        chain_id=str(chain_id),
        res_seq=int(res_seq),
        i_code=str(i_code),
        occupancy=float(occ),
        element=str(element),
        charge=str(charge),
    )
    return atom, np.asarray([x, y, z], dtype=np.float32)


def _infer_meta_from_name(path: str) -> Tuple[str, int, int]:
    base = os.path.basename(str(path))
    m = re.search(r"internal_post_(.+?)_sample(\d+)_step(\d+)\.pdb$", base, flags=re.IGNORECASE)
    if not m:
        m = re.search(r"visual_post_(.+?)_sample(\d+)_step(\d+)\.pdb$", base, flags=re.IGNORECASE)
    if not m:
        return _slug(os.path.splitext(base)[0]), 0, 0
    return _slug(m.group(1)), _safe_int(m.group(2), 0), _safe_int(m.group(3), 0)


def _parse_pdb(path: str) -> Optional[PdbFrame]:
    try:
        lines = open(path, "r", encoding="utf-8", errors="ignore").read().splitlines()
    except Exception:
        return None
    if not lines:
        return None

    fallback_target, fallback_sample, fallback_step = _infer_meta_from_name(path)
    target = fallback_target
    sample_idx = fallback_sample
    step = fallback_step
    atoms: List[AtomRecord] = []
    coords: List[np.ndarray] = []
    headers: List[str] = []
    ters: List[str] = []
    conects: List[str] = []
    for ln in lines:
        if ln.startswith("REMARK TARGET "):
            target = _slug(ln.replace("REMARK TARGET ", "", 1).strip())
            headers.append(ln)
            continue
        if ln.startswith("REMARK SAMPLE_IDX "):
            sample_idx = _safe_int(ln.replace("REMARK SAMPLE_IDX ", "", 1), sample_idx)
            headers.append(ln)
            continue
        if ln.startswith("REMARK STEP "):
            step = _safe_int(ln.replace("REMARK STEP ", "", 1), step)
            headers.append(ln)
            continue
        if ln.startswith("ATOM") or ln.startswith("HETATM"):
            atom, xyz = _parse_atom_line(ln)
            atoms.append(atom)
            coords.append(xyz)
            continue
        if ln.startswith("CONECT"):
            conects.append(ln)
            continue
        if ln.startswith("TER"):
            ters.append(ln)
            continue
        if ln.startswith("END"):
            continue
        if ln.startswith("HELIX") or ln.startswith("SHEET"):
            # Re-generated from refined geometry.
            continue
        headers.append(ln)

    if not atoms:
        return None

    return PdbFrame(
        path=str(path),
        target=str(target),
        sample_idx=int(sample_idx),
        step=int(step),
        atoms=atoms,
        coords=np.stack(coords, axis=0).astype(np.float32, copy=False),
        headers=headers,
        ters=ters,
        conects=conects,
    )


def _kabsch_align(mobile: np.ndarray, ref: np.ndarray) -> np.ndarray:
    m = np.asarray(mobile, dtype=np.float64)
    r = np.asarray(ref, dtype=np.float64)
    m0 = m - np.mean(m, axis=0, keepdims=True)
    r0 = r - np.mean(r, axis=0, keepdims=True)
    h = m0.T @ r0
    u, _s, vt = np.linalg.svd(h)
    rot = vt.T @ u.T
    if np.linalg.det(rot) < 0:
        vt[-1, :] *= -1.0
        rot = vt.T @ u.T
    aligned = (m0 @ rot) + np.mean(r, axis=0, keepdims=True)
    return aligned.astype(np.float32, copy=False)


def _align_stack(stack: np.ndarray) -> np.ndarray:
    arr = np.asarray(stack, dtype=np.float32)
    if arr.ndim != 3 or arr.shape[0] <= 1:
        return arr
    ref = arr[0]
    out = np.zeros_like(arr, dtype=np.float32)
    out[0] = ref
    for i in range(1, arr.shape[0]):
        out[i] = _kabsch_align(arr[i], ref)
    return out


def _smooth_stack(stack: np.ndarray, window: int) -> np.ndarray:
    arr = np.asarray(stack, dtype=np.float32)
    if arr.ndim != 3 or int(window) <= 1 or arr.shape[0] <= 1:
        return arr
    half = max(0, int(window) // 2)
    out = np.zeros_like(arr, dtype=np.float32)
    for i in range(arr.shape[0]):
        lo = max(0, i - half)
        hi = min(arr.shape[0], i + half + 1)
        out[i] = np.mean(arr[lo:hi], axis=0)
    return out


def _local_curvature_proxy(coords: np.ndarray) -> np.ndarray:
    c = np.asarray(coords, dtype=np.float32)
    n = int(c.shape[0]) if c.ndim == 2 else 0
    out = np.zeros((n,), dtype=np.float32)
    if n <= 2:
        return out
    d2 = c[:-2] - (2.0 * c[1:-1]) + c[2:]
    out[1:-1] = np.linalg.norm(d2, axis=1).astype(np.float32, copy=False)
    out[0] = out[1]
    out[-1] = out[-2]
    return out


def _map_to_bfactor(values: np.ndarray) -> np.ndarray:
    vals = np.asarray(values, dtype=np.float32).reshape(-1)
    if vals.size <= 0:
        return vals
    lo = float(np.percentile(vals, 5.0))
    hi = float(np.percentile(vals, 95.0))
    if (not math.isfinite(lo)) or (not math.isfinite(hi)) or (hi - lo <= 1e-8):
        return np.full_like(vals, 50.0, dtype=np.float32)
    x = (vals - lo) / (hi - lo)
    x = np.clip(x, 0.0, 1.0)
    return (x * 100.0).astype(np.float32, copy=False)


def _unit_vec(v: np.ndarray) -> np.ndarray:
    x = np.asarray(v, dtype=np.float32).reshape(3)
    n = float(np.linalg.norm(x))
    if (not math.isfinite(n)) or (n <= 1e-8):
        return np.asarray([1.0, 0.0, 0.0], dtype=np.float32)
    return (x / n).astype(np.float32, copy=False)


def _orthogonal_unit(v: np.ndarray) -> np.ndarray:
    base = _unit_vec(v)
    axis = np.asarray([0.0, 0.0, 1.0], dtype=np.float32)
    if abs(float(np.dot(base, axis))) > 0.9:
        axis = np.asarray([0.0, 1.0, 0.0], dtype=np.float32)
    out = np.cross(base, axis)
    return _unit_vec(out)


def _build_backbone_frames(ca_coords: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    ca = np.asarray(ca_coords, dtype=np.float32)
    n = int(ca.shape[0]) if ca.ndim == 2 else 0
    tangents = np.zeros((n, 3), dtype=np.float32)
    normals = np.zeros((n, 3), dtype=np.float32)
    binormals = np.zeros((n, 3), dtype=np.float32)
    if n <= 0:
        return tangents, normals, binormals

    prev_normal = np.asarray([0.0, 1.0, 0.0], dtype=np.float32)
    for i in range(n):
        if n == 1:
            t = np.asarray([1.0, 0.0, 0.0], dtype=np.float32)
        elif i == 0:
            t = _unit_vec(ca[1] - ca[0])
        elif i == (n - 1):
            t = _unit_vec(ca[-1] - ca[-2])
        else:
            t = _unit_vec(ca[i + 1] - ca[i - 1])

        if 0 < i < (n - 1):
            curv = ca[i + 1] - (2.0 * ca[i]) + ca[i - 1]
            nvec = _unit_vec(curv) if float(np.linalg.norm(curv)) > 1e-5 else prev_normal
        else:
            nvec = prev_normal

        bvec = np.cross(t, nvec)
        if float(np.linalg.norm(bvec)) <= 1e-5:
            nvec = _orthogonal_unit(t)
            bvec = np.cross(t, nvec)
        bvec = _unit_vec(bvec)
        nvec = _unit_vec(np.cross(bvec, t))

        tangents[i] = t
        normals[i] = nvec
        binormals[i] = bvec
        prev_normal = nvec
    return tangents, normals, binormals


def _apply_visual_residual_single(
    coords: np.ndarray,
    *,
    residual_lambda: float,
    residual_iters: int,
    target_ca_dist: float,
) -> np.ndarray:
    c = np.asarray(coords, dtype=np.float32).copy()
    n = int(c.shape[0]) if c.ndim == 2 else 0
    if n <= 2:
        return c
    lam = max(0.0, float(residual_lambda))
    iters = max(0, int(residual_iters))
    target = max(0.5, float(target_ca_dist))
    if lam <= 0.0 or iters <= 0:
        return c

    for _ in range(iters):
        lap = c[:-2] - (2.0 * c[1:-1]) + c[2:]
        c[1:-1] = c[1:-1] + (lam * lap)

        seg = c[1:] - c[:-1]
        seg_len = np.linalg.norm(seg, axis=1)
        for i in range(n - 1):
            ln = float(seg_len[i])
            if ln <= 1e-6:
                continue
            direction = seg[i] / ln
            delta = 0.5 * (target - ln) * direction
            if i == 0:
                c[i + 1] += 0.7 * delta
            elif i == (n - 2):
                c[i] -= 0.7 * delta
            else:
                c[i] -= delta
                c[i + 1] += delta
    return c


def _apply_visual_residual_stack(
    stack: np.ndarray,
    *,
    residual_lambda: float,
    residual_iters: int,
    target_ca_dist: float,
) -> np.ndarray:
    arr = np.asarray(stack, dtype=np.float32)
    if arr.ndim != 3 or arr.shape[0] <= 0:
        return arr
    out = np.zeros_like(arr, dtype=np.float32)
    for i in range(arr.shape[0]):
        out[i] = _apply_visual_residual_single(
            arr[i],
            residual_lambda=residual_lambda,
            residual_iters=residual_iters,
            target_ca_dist=target_ca_dist,
        )
    return out


def _estimate_flexibility(stack: np.ndarray) -> Tuple[np.ndarray, str]:
    arr = np.asarray(stack, dtype=np.float32)
    if arr.ndim != 3 or arr.shape[1] <= 0:
        return np.zeros((0,), dtype=np.float32), "none"
    if arr.shape[0] >= 2:
        mu = np.mean(arr, axis=0, keepdims=True)
        rmsf = np.sqrt(np.mean(np.sum((arr - mu) ** 2, axis=-1), axis=0))
        return _map_to_bfactor(rmsf), "rmsf"
    proxy = _local_curvature_proxy(arr[0])
    return _map_to_bfactor(proxy), "curvature_proxy_single_frame"


def _is_ca_only_frame(frame: PdbFrame) -> bool:
    names = [str(a.atom_name).strip().upper() for a in frame.atoms]
    return bool(names) and all(x == "CA" for x in names)


def _residue_key(atom: AtomRecord) -> Tuple[str, int, str, str]:
    return (
        str(atom.chain_id).strip() or "A",
        int(atom.res_seq),
        str(atom.i_code).strip(),
        str(atom.res_name).strip() or "GLY",
    )


def _collect_ca_trace_by_residue(atoms: Sequence[AtomRecord], coords: np.ndarray) -> np.ndarray:
    xyz = np.asarray(coords, dtype=np.float32)
    residue_order: List[Tuple[str, int, str, str]] = []
    residue_atoms: Dict[Tuple[str, int, str, str], List[np.ndarray]] = {}
    residue_ca: Dict[Tuple[str, int, str, str], np.ndarray] = {}
    for atom, pos in zip(atoms, xyz):
        key = _residue_key(atom)
        if key not in residue_atoms:
            residue_order.append(key)
            residue_atoms[key] = []
        residue_atoms[key].append(np.asarray(pos, dtype=np.float32))
        if str(atom.atom_name).strip().upper() == "CA":
            residue_ca[key] = np.asarray(pos, dtype=np.float32)
    out: List[np.ndarray] = []
    for key in residue_order:
        if key in residue_ca:
            out.append(residue_ca[key])
        else:
            aa = residue_atoms.get(key, [])
            if aa:
                out.append(np.mean(np.stack(aa, axis=0), axis=0).astype(np.float32, copy=False))
    if not out:
        return np.zeros((0, 3), dtype=np.float32)
    return np.stack(out, axis=0).astype(np.float32, copy=False)


def _collect_backbone_coords_by_residue(
    atoms: Sequence[AtomRecord], coords: np.ndarray
) -> Tuple[List[Tuple[str, int, str, str]], np.ndarray]:
    xyz = np.asarray(coords, dtype=np.float32)
    residue_order: List[Tuple[str, int, str, str]] = []
    residue_bb: Dict[Tuple[str, int, str, str], Dict[str, np.ndarray]] = {}
    for atom, pos in zip(atoms, xyz):
        key = _residue_key(atom)
        if key not in residue_bb:
            residue_order.append(key)
            residue_bb[key] = {}
        name = str(atom.atom_name).strip().upper()
        if name in {"N", "CA", "C", "O"} and name not in residue_bb[key]:
            residue_bb[key][name] = np.asarray(pos, dtype=np.float32)

    keys_out: List[Tuple[str, int, str, str]] = []
    bb_out: List[np.ndarray] = []
    for key in residue_order:
        bb = residue_bb.get(key, {})
        if not all(k in bb for k in ("N", "CA", "C", "O")):
            continue
        keys_out.append(key)
        bb_out.append(
            np.stack([bb["N"], bb["CA"], bb["C"], bb["O"]], axis=0).astype(np.float32, copy=False)
        )
    if not bb_out:
        return keys_out, np.zeros((0, 4, 3), dtype=np.float32)
    return keys_out, np.stack(bb_out, axis=0).astype(np.float32, copy=False)


def _runs_from_c3_labels(labels: Sequence[str]) -> Tuple[List[str], List[Tuple[int, int]], List[Tuple[int, int]]]:
    norm = []
    for lab in labels:
        t = str(lab).strip().upper()
        if t == "H":
            norm.append("H")
        elif t == "E":
            norm.append("E")
        else:
            norm.append("C")
    cleaned = _clean_runs(_clean_runs(norm, "H", 4), "E", 3)
    helix_runs, sheet_runs = _labels_to_runs(cleaned)
    return cleaned, helix_runs, sheet_runs


def _assign_secondary_structure_dssp(
    atoms: Sequence[AtomRecord], coords: np.ndarray
) -> Optional[Tuple[List[str], List[Tuple[int, int]], List[Tuple[int, int]], str]]:
    if _pydssp is None:
        return None
    _keys, bb = _collect_backbone_coords_by_residue(atoms, coords)
    if bb.ndim != 3 or bb.shape[0] < 4:
        return None
    try:
        c3 = _pydssp.assign(bb.astype(np.float32, copy=False), out_type="c3")
    except Exception:
        return None
    arr = np.asarray(c3).reshape(-1)
    if arr.size <= 0:
        return None
    labels, helix_runs, sheet_runs = _runs_from_c3_labels([str(x) for x in arr])
    return labels, helix_runs, sheet_runs, "dssp_pydssp_v1"


def _expand_pseudo_backbone(
    frame: PdbFrame,
    ca_coords: np.ndarray,
    ca_bfactor: np.ndarray,
) -> Tuple[List[AtomRecord], np.ndarray, np.ndarray]:
    ca = np.asarray(ca_coords, dtype=np.float32)
    bf = np.asarray(ca_bfactor, dtype=np.float32).reshape(-1)
    n = int(ca.shape[0]) if ca.ndim == 2 else 0
    if n <= 0:
        return [], np.zeros((0, 3), dtype=np.float32), np.zeros((0,), dtype=np.float32)

    tangents, normals, binormals = _build_backbone_frames(ca)
    out_atoms: List[AtomRecord] = []
    out_coords: List[np.ndarray] = []
    out_bf: List[float] = []
    serial = 1

    for i in range(n):
        src = frame.atoms[min(i, len(frame.atoms) - 1)]
        ca_i = ca[i]
        t = tangents[i]
        nv = normals[i]
        bv = binormals[i]
        bf_i = float(bf[i]) if i < bf.size else 50.0

        n_pos = ca_i - (1.18 * t) + (0.32 * nv)
        c_pos = ca_i + (1.25 * t) + (0.20 * nv)
        o_pos = c_pos + (1.02 * nv) + (0.18 * bv)
        entries = [
            ("N", "N", n_pos),
            ("CA", "C", ca_i),
            ("C", "C", c_pos),
            ("O", "O", o_pos),
        ]
        for atom_name, elem, xyz in entries:
            out_atoms.append(
                AtomRecord(
                    record_name="ATOM",
                    serial=int(serial),
                    atom_name=str(atom_name),
                    alt_loc="",
                    res_name=str(src.res_name) if str(src.res_name).strip() else "GLY",
                    chain_id=str(src.chain_id) if str(src.chain_id).strip() else "A",
                    res_seq=int(src.res_seq),
                    i_code=str(src.i_code),
                    occupancy=float(src.occupancy),
                    element=str(elem),
                    charge="",
                )
            )
            out_coords.append(np.asarray(xyz, dtype=np.float32))
            out_bf.append(float(bf_i))
            serial += 1

    return out_atoms, np.stack(out_coords, axis=0).astype(np.float32, copy=False), np.asarray(out_bf, dtype=np.float32)


def _bond_angles(coords: np.ndarray) -> np.ndarray:
    c = np.asarray(coords, dtype=np.float32)
    n = int(c.shape[0]) if c.ndim == 2 else 0
    out = np.full((n,), np.nan, dtype=np.float32)
    if n < 3:
        return out
    v1 = c[:-2] - c[1:-1]
    v2 = c[2:] - c[1:-1]
    n1 = np.linalg.norm(v1, axis=1)
    n2 = np.linalg.norm(v2, axis=1)
    denom = np.maximum(n1 * n2, 1e-8)
    cosv = np.sum(v1 * v2, axis=1) / denom
    cosv = np.clip(cosv, -1.0, 1.0)
    out[1:-1] = np.arccos(cosv).astype(np.float32, copy=False)
    return out


def _dihedrals(coords: np.ndarray) -> np.ndarray:
    c = np.asarray(coords, dtype=np.float32)
    n = int(c.shape[0]) if c.ndim == 2 else 0
    out = np.full((n,), np.nan, dtype=np.float32)
    if n < 4:
        return out
    p0, p1, p2, p3 = c[:-3], c[1:-2], c[2:-1], c[3:]
    b0 = p1 - p0
    b1 = p2 - p1
    b2 = p3 - p2
    b1n = b1 / np.maximum(np.linalg.norm(b1, axis=1, keepdims=True), 1e-8)
    v = b0 - np.sum(b0 * b1n, axis=1, keepdims=True) * b1n
    w = b2 - np.sum(b2 * b1n, axis=1, keepdims=True) * b1n
    x = np.sum(v * w, axis=1)
    y = np.sum(np.cross(b1n, v) * w, axis=1)
    phi = np.arctan2(y, x).astype(np.float32, copy=False)
    out[1:-2] = phi
    return out


def _clean_runs(labels: List[str], symbol: str, min_len: int) -> List[str]:
    out = list(labels)
    n = len(out)
    i = 0
    while i < n:
        if out[i] != symbol:
            i += 1
            continue
        j = i + 1
        while j < n and out[j] == symbol:
            j += 1
        if (j - i) < int(min_len):
            for k in range(i, j):
                out[k] = "C"
        i = j
    return out


def _labels_to_runs(labels: Sequence[str]) -> Tuple[List[Tuple[int, int]], List[Tuple[int, int]]]:
    helix_runs: List[Tuple[int, int]] = []
    sheet_runs: List[Tuple[int, int]] = []
    n = int(len(labels))
    i = 0
    while i < n:
        lab = str(labels[i]).strip().upper()
        if lab not in {"H", "E"}:
            i += 1
            continue
        j = i + 1
        while j < n and str(labels[j]).strip().upper() == lab:
            j += 1
        run = (i + 1, j)  # 1-based inclusive
        if lab == "H":
            helix_runs.append(run)
        else:
            sheet_runs.append(run)
        i = j
    return helix_runs, sheet_runs


def _majority_token(tokens: Sequence[str]) -> str:
    counts: Dict[str, int] = {}
    for tok in tokens:
        key = str(tok).strip()
        if not key:
            continue
        counts[key] = int(counts.get(key, 0)) + 1
    if not counts:
        return ""
    best_key = ""
    best_count = -1
    for k, v in counts.items():
        if int(v) > int(best_count):
            best_key = str(k)
            best_count = int(v)
    return best_key


def _temporal_vote_secondary_labels(
    labels_by_frame: Sequence[Sequence[str]],
    *,
    min_fraction: float,
) -> Optional[Tuple[List[str], List[Tuple[int, int]], List[Tuple[int, int]]]]:
    seqs: List[List[str]] = []
    for labels in labels_by_frame:
        norm: List[str] = []
        for lab in labels:
            tok = str(lab).strip().upper()
            if tok not in {"H", "E"}:
                tok = "C"
            norm.append(tok)
        if norm:
            seqs.append(norm)
    if not seqs:
        return None
    n = int(len(seqs[0]))
    if n <= 0:
        return None
    if any(int(len(x)) != n for x in seqs):
        return None

    ref = seqs[-1]
    frac_min = float(np.clip(float(min_fraction), 0.0, 1.0))
    voted: List[str] = []
    for i in range(n):
        h = 0
        e = 0
        c = 0
        for frame_labels in seqs:
            tok = frame_labels[i]
            if tok == "H":
                h += 1
            elif tok == "E":
                e += 1
            else:
                c += 1
        best = ref[i] if ref[i] in {"H", "E", "C"} else "C"
        best_count = -1
        for tok, cnt in [("H", h), ("E", e), ("C", c)]:
            if cnt > best_count:
                best = tok
                best_count = int(cnt)
            elif (cnt == best_count) and (tok == ref[i]):
                best = tok
        frac = float(best_count) / float(len(seqs))
        if frac < frac_min:
            best = ref[i] if ref[i] in {"H", "E", "C"} else "C"
        voted.append(best)

    cleaned = _clean_runs(_clean_runs(voted, "H", 4), "E", 3)
    helix_runs, sheet_runs = _labels_to_runs(cleaned)
    return cleaned, helix_runs, sheet_runs


def _assign_secondary_structure(coords: np.ndarray) -> Tuple[List[str], List[Tuple[int, int]], List[Tuple[int, int]], str]:
    c = np.asarray(coords, dtype=np.float32)
    n = int(c.shape[0]) if c.ndim == 2 else 0
    if n <= 0:
        return [], [], [], "none"
    theta = _bond_angles(c)
    phi = _dihedrals(c)
    labels = ["C"] * n
    for i in range(n):
        t = float(theta[i]) if np.isfinite(theta[i]) else float("nan")
        p = float(phi[i]) if np.isfinite(phi[i]) else float("nan")
        if (not math.isfinite(t)) or (not math.isfinite(p)):
            continue
        if (1.20 <= t <= 2.20) and (-1.70 <= p <= -0.20):
            labels[i] = "H"
        elif (1.75 <= t <= 2.80) and (abs(p) >= 2.20):
            labels[i] = "E"
        else:
            labels[i] = "C"
    labels = _clean_runs(_clean_runs(labels, "H", 4), "E", 3)
    helix_runs, sheet_runs = _labels_to_runs(labels)
    return labels, helix_runs, sheet_runs, "dssp_ca_heuristic_v1"


def _assign_secondary_structure_for_render(
    atoms: Sequence[AtomRecord],
    coords: np.ndarray,
    *,
    mode: str,
) -> Tuple[List[str], List[Tuple[int, int]], List[Tuple[int, int]], str]:
    mode_tok = str(mode).strip().lower() or "auto"
    if mode_tok in {"auto", "dssp"}:
        got = _assign_secondary_structure_dssp(atoms, coords)
        if got is not None:
            return got
    ca_trace = _collect_ca_trace_by_residue(atoms, coords)
    labels, helix_runs, sheet_runs, sec_method = _assign_secondary_structure(ca_trace)
    if mode_tok == "dssp":
        sec_method = "dssp_pydssp_unavailable_fallback_ca_heuristic_v1"
    return labels, helix_runs, sheet_runs, sec_method


def _format_atom(atom: AtomRecord, xyz: np.ndarray, bfactor: float) -> str:
    x, y, z = [float(v) for v in np.asarray(xyz, dtype=np.float32).reshape(3)]
    line = (
        f"{atom.record_name:<6}{int(atom.serial):5d} "
        f"{str(atom.atom_name):>4}{str(atom.alt_loc):1}"
        f"{str(atom.res_name):>3} {str(atom.chain_id):1}"
        f"{int(atom.res_seq):4d}{str(atom.i_code):1}   "
        f"{x:8.3f}{y:8.3f}{z:8.3f}"
        f"{float(atom.occupancy):6.2f}{float(bfactor):6.2f}          "
        f"{str(atom.element):>2}{str(atom.charge):>2}"
    )
    return line


def _write_pdb(
    out_path: str,
    frame: PdbFrame,
    atoms: Sequence[AtomRecord],
    coords: np.ndarray,
    bfactor: np.ndarray,
    helix_runs: Sequence[Tuple[int, int]],
    sheet_runs: Sequence[Tuple[int, int]],
    sec_method: str,
    flex_method: str,
    visual_model: str,
    write_conect: bool,
) -> None:
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for ln in frame.headers:
            if ln.startswith("REMARK SOURCE "):
                continue
            f.write(f"{ln}\n")
        f.write("REMARK SOURCE internal_visual_refined\n")
        f.write("REMARK VISUAL_PIPELINE postprocess_structure_visuals.py\n")
        f.write(f"REMARK VISUAL_MODEL {visual_model}\n")
        f.write(f"REMARK SECONDARY_STRUCTURE_METHOD {sec_method}\n")
        f.write(f"REMARK FLEXIBILITY_METHOD {flex_method}\n")
        for h_idx, (start, end) in enumerate(helix_runs, start=1):
            f.write(
                f"HELIX  {h_idx:3d} {h_idx:3d} GLY A{int(start):4d}  GLY A{int(end):4d}  1"
                f"{'':30s}{int(end - start + 1):5d}\n"
            )
        for s_idx, (start, end) in enumerate(sheet_runs, start=1):
            f.write(
                f"SHEET  {s_idx:3d} A 1 GLY A{int(start):4d}  GLY A{int(end):4d}  0\n"
            )
        for i, atom in enumerate(atoms):
            bf = float(bfactor[i]) if i < len(bfactor) else 50.0
            f.write(_format_atom(atom, coords[i], bf) + "\n")
        if write_conect and frame.ters:
            for ln in frame.ters:
                f.write(f"{ln}\n")
        elif atoms:
            last = atoms[-1]
            f.write(
                f"TER   {int(last.serial + 1):5d}      {str(last.res_name):>3} "
                f"{str(last.chain_id):1}{int(last.res_seq):4d}\n"
            )
        if write_conect:
            for ln in frame.conects:
                f.write(f"{ln}\n")
        f.write("END\n")


def _process_group(
    target: str,
    frames: List[PdbFrame],
    *,
    secondary_structure_mode: str,
    align: bool,
    smooth_window: int,
    residual_lambda: float,
    residual_iters: int,
    target_ca_dist: float,
    residual_bfactor_weight: float,
    pseudo_backbone: bool,
    ss_temporal_vote: bool,
    ss_vote_min_fraction: float,
    ss_vote_min_frames: int,
    out_dir: str,
    name_prefix: str,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not frames:
        return rows
    frames = sorted(frames, key=lambda x: (int(x.step), int(x.sample_idx), str(x.path)))
    n_atoms = int(frames[0].coords.shape[0])
    homogeneous = all(int(fr.coords.shape[0]) == n_atoms for fr in frames)
    if not homogeneous:
        # Fallback: process one-by-one.
        for fr in frames:
            base_coords = np.asarray(fr.coords, dtype=np.float32)
            corr_coords = _apply_visual_residual_single(
                base_coords,
                residual_lambda=residual_lambda,
                residual_iters=residual_iters,
                target_ca_dist=target_ca_dist,
            )
            corr_mag = np.linalg.norm(corr_coords - base_coords, axis=1).astype(np.float32, copy=False)
            flex = _map_to_bfactor(_local_curvature_proxy(corr_coords))
            corr_b = _map_to_bfactor(corr_mag)
            rw = float(np.clip(float(residual_bfactor_weight), 0.0, 1.0))
            mix_b = np.clip(((1.0 - rw) * flex) + (rw * corr_b), 0.0, 100.0).astype(np.float32, copy=False)
            _labels, helix_runs, sheet_runs, sec_method = _assign_secondary_structure(corr_coords)
            out_name = f"{name_prefix}{os.path.basename(fr.path)}"
            out_path = os.path.join(out_dir, out_name)
            use_pseudo = bool(pseudo_backbone) and _is_ca_only_frame(fr)
            if use_pseudo:
                out_atoms, out_coords, out_b = _expand_pseudo_backbone(fr, corr_coords, mix_b)
                visual_model = "pseudo_backbone_v1"
                write_conect = False
            else:
                out_atoms = list(fr.atoms)
                out_coords = corr_coords
                out_b = mix_b
                visual_model = "native_atoms_refined"
                write_conect = True
            _labels, helix_runs, sheet_runs, sec_method = _assign_secondary_structure_for_render(
                out_atoms,
                out_coords,
                mode=secondary_structure_mode,
            )
            _write_pdb(
                out_path=out_path,
                frame=fr,
                atoms=out_atoms,
                coords=out_coords,
                bfactor=out_b,
                helix_runs=helix_runs,
                sheet_runs=sheet_runs,
                sec_method=sec_method,
                flex_method="curvature_proxy_mismatch+residual_mix_v1",
                visual_model=visual_model,
                write_conect=write_conect,
            )
            rows.append(
                {
                    "target": target,
                    "source_path": fr.path,
                    "out_path": out_path,
                    "atoms": int(out_coords.shape[0]),
                    "frames_in_target": int(len(frames)),
                    "step": int(fr.step),
                    "sample_idx": int(fr.sample_idx),
                    "flex_method": "curvature_proxy_mismatch+residual_mix_v1",
                    "sec_method": sec_method,
                    "visual_model": visual_model,
                    "bfactor_min": float(np.min(out_b)) if out_b.size else None,
                    "bfactor_max": float(np.max(out_b)) if out_b.size else None,
                }
            )
        return rows

    stack = np.stack([fr.coords for fr in frames], axis=0).astype(np.float32, copy=False)
    if align:
        stack = _align_stack(stack)
    stack = _smooth_stack(stack, int(smooth_window))
    stack_before_residual = np.asarray(stack, dtype=np.float32).copy()
    stack = _apply_visual_residual_stack(
        stack,
        residual_lambda=residual_lambda,
        residual_iters=residual_iters,
        target_ca_dist=target_ca_dist,
    )
    bfactor, flex_method = _estimate_flexibility(stack)
    corr_mag = np.mean(np.linalg.norm(stack - stack_before_residual, axis=2), axis=0)
    corr_b = _map_to_bfactor(corr_mag)
    rw = float(np.clip(float(residual_bfactor_weight), 0.0, 1.0))
    bfactor = np.clip(((1.0 - rw) * bfactor) + (rw * corr_b), 0.0, 100.0).astype(np.float32, copy=False)
    flex_method = f"{flex_method}+residual_mix_v1"
    sec_method = ""
    helix_runs: List[Tuple[int, int]] = []
    sheet_runs: List[Tuple[int, int]] = []
    use_temporal_vote = bool(ss_temporal_vote) and int(len(frames)) >= max(2, int(ss_vote_min_frames))
    if use_temporal_vote:
        labels_stack: List[List[str]] = []
        methods: List[str] = []
        for i, fr in enumerate(frames):
            use_pseudo_i = bool(pseudo_backbone) and _is_ca_only_frame(fr)
            if use_pseudo_i:
                atoms_i, coords_i, _b_i = _expand_pseudo_backbone(fr, stack[i], bfactor)
            else:
                atoms_i = list(fr.atoms)
                coords_i = stack[i]
            labels_i, _h_i, _s_i, method_i = _assign_secondary_structure_for_render(
                atoms_i,
                coords_i,
                mode=secondary_structure_mode,
            )
            if labels_i:
                labels_stack.append(labels_i)
                methods.append(method_i)
        voted = _temporal_vote_secondary_labels(
            labels_stack,
            min_fraction=float(ss_vote_min_fraction),
        )
        if voted is not None:
            _voted_labels, helix_runs, sheet_runs = voted
            method_base = _majority_token(methods) or "secondary_structure_unknown_v1"
            sec_method = f"{method_base}+temporal_vote_v1"

    if not sec_method:
        representative = stack[-1]
        use_pseudo_ref = bool(pseudo_backbone) and _is_ca_only_frame(frames[0])
        if use_pseudo_ref:
            rep_atoms, rep_coords, _rep_b = _expand_pseudo_backbone(frames[0], representative, bfactor)
        else:
            rep_atoms = list(frames[0].atoms)
            rep_coords = representative
        _labels, helix_runs, sheet_runs, sec_method = _assign_secondary_structure_for_render(
            rep_atoms,
            rep_coords,
            mode=secondary_structure_mode,
        )

    for i, fr in enumerate(frames):
        out_name = f"{name_prefix}{os.path.basename(fr.path)}"
        out_path = os.path.join(out_dir, out_name)
        use_pseudo = bool(pseudo_backbone) and _is_ca_only_frame(fr)
        if use_pseudo:
            out_atoms, out_coords, out_b = _expand_pseudo_backbone(fr, stack[i], bfactor)
            visual_model = "pseudo_backbone_v1"
            write_conect = False
        else:
            out_atoms = list(fr.atoms)
            out_coords = stack[i]
            out_b = bfactor
            visual_model = "native_atoms_refined"
            write_conect = True
        _write_pdb(
            out_path=out_path,
            frame=fr,
            atoms=out_atoms,
            coords=out_coords,
            bfactor=out_b,
            helix_runs=helix_runs,
            sheet_runs=sheet_runs,
            sec_method=sec_method,
            flex_method=flex_method,
            visual_model=visual_model,
            write_conect=write_conect,
        )
        rows.append(
            {
                "target": target,
                "source_path": fr.path,
                "out_path": out_path,
                "atoms": int(out_coords.shape[0]),
                "frames_in_target": int(len(frames)),
                "step": int(fr.step),
                "sample_idx": int(fr.sample_idx),
                "flex_method": flex_method,
                "sec_method": sec_method,
                "visual_model": visual_model,
                "bfactor_min": float(np.min(out_b)) if out_b.size else None,
                "bfactor_max": float(np.max(out_b)) if out_b.size else None,
            }
        )
    return rows


def run(args: argparse.Namespace) -> Dict[str, Any]:
    inputs = _collect_inputs(args.in_pdb, args.in_glob)
    frames: List[PdbFrame] = []
    for p in inputs:
        fr = _parse_pdb(p)
        if fr is not None:
            frames.append(fr)

    grouped: Dict[str, List[PdbFrame]] = {}
    for fr in frames:
        grouped.setdefault(str(fr.target), []).append(fr)

    os.makedirs(args.out_dir, exist_ok=True)
    all_rows: List[Dict[str, Any]] = []
    for target, group in grouped.items():
        rows = _process_group(
            target=target,
            frames=group,
            secondary_structure_mode=str(args.secondary_structure_mode),
            align=bool(args.align),
            smooth_window=int(args.smooth_window),
            residual_lambda=float(args.visual_residual_lambda),
            residual_iters=int(args.visual_residual_iters),
            target_ca_dist=float(args.target_ca_distance),
            residual_bfactor_weight=float(args.residual_bfactor_weight),
            pseudo_backbone=bool(args.pseudo_backbone),
            ss_temporal_vote=bool(args.ss_temporal_vote),
            ss_vote_min_fraction=float(args.ss_vote_min_fraction),
            ss_vote_min_frames=int(args.ss_vote_min_frames),
            out_dir=str(args.out_dir),
            name_prefix=str(args.name_prefix),
        )
        all_rows.extend(rows)

    if args.out_csv:
        os.makedirs(os.path.dirname(args.out_csv) or ".", exist_ok=True)
        keys = [
            "target",
            "source_path",
            "out_path",
            "atoms",
            "frames_in_target",
            "step",
            "sample_idx",
            "flex_method",
            "sec_method",
            "visual_model",
            "bfactor_min",
            "bfactor_max",
        ]
        with open(args.out_csv, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            for row in all_rows:
                w.writerow(row)

    summary = {
        "ok": True,
        "inputs_count": int(len(inputs)),
        "parsed_frames": int(len(frames)),
        "targets_count": int(len(grouped)),
        "processed_frames": int(len(all_rows)),
        "out_dir": str(args.out_dir),
        "out_csv": str(args.out_csv),
        "align": bool(args.align),
        "smooth_window": int(args.smooth_window),
        "secondary_structure_mode": str(args.secondary_structure_mode),
        "visual_residual_lambda": float(args.visual_residual_lambda),
        "visual_residual_iters": int(args.visual_residual_iters),
        "target_ca_distance": float(args.target_ca_distance),
        "residual_bfactor_weight": float(args.residual_bfactor_weight),
        "pseudo_backbone": bool(args.pseudo_backbone),
        "ss_temporal_vote": bool(args.ss_temporal_vote),
        "ss_vote_min_fraction": float(args.ss_vote_min_fraction),
        "ss_vote_min_frames": int(args.ss_vote_min_frames),
        "name_prefix": str(args.name_prefix),
        "rows": all_rows[:2000],
    }
    if (not all_rows) and bool(args.fail_on_empty):
        summary["ok"] = False
        summary["error"] = "no_frames_processed"

    if args.out_json:
        os.makedirs(os.path.dirname(args.out_json) or ".", exist_ok=True)
        with open(args.out_json, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
    return summary


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Refine raw PDB snapshots for dashboard rendering: alignment, smoothing, B-factor flexibility map."
    )
    p.add_argument("--in-pdb", action="append", default=[], help="Input PDB file path (repeatable).")
    p.add_argument("--in-glob", action="append", default=[], help="Input glob pattern(s) for PDB files.")
    p.add_argument("--out-dir", type=str, required=True, help="Directory for refined PDB outputs.")
    p.add_argument("--out-csv", type=str, default="", help="Optional processing report CSV.")
    p.add_argument("--out-json", type=str, default="", help="Optional processing summary JSON.")
    p.add_argument("--align", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--smooth-window", type=int, default=3)
    p.add_argument(
        "--secondary-structure-mode",
        type=str,
        choices=["auto", "dssp", "heuristic"],
        default="auto",
        help="Secondary structure assignment backend. auto prefers DSSP and falls back to heuristic.",
    )
    p.add_argument("--visual-residual-lambda", type=float, default=0.12)
    p.add_argument("--visual-residual-iters", type=int, default=2)
    p.add_argument("--target-ca-distance", type=float, default=3.8)
    p.add_argument("--residual-bfactor-weight", type=float, default=0.25)
    p.add_argument("--pseudo-backbone", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--ss-temporal-vote", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--ss-vote-min-fraction", type=float, default=0.60)
    p.add_argument("--ss-vote-min-frames", type=int, default=3)
    p.add_argument("--name-prefix", type=str, default="visual_post_")
    p.add_argument("--fail-on-empty", action=argparse.BooleanOptionalAction, default=False)
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    summary = run(args)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if not bool(summary.get("ok", False)):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
