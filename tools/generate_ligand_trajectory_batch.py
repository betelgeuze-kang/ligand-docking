#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from tools.pdb_loader import load_native_structure


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return float(default)
        s = str(v).strip()
        if (not s) or (s.lower() == "nan"):
            return float(default)
        return float(s)
    except Exception:
        return float(default)


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(float(v))
    except Exception:
        return int(default)


def _slug(text: str) -> str:
    out: List[str] = []
    prev_us = False
    for ch in str(text).strip().lower():
        if ch.isalnum():
            out.append(ch)
            prev_us = False
            continue
        if not prev_us:
            out.append("_")
            prev_us = True
    s = "".join(out).strip("_")
    return s or "target"


def _parse_pdb_ca_or_atom_coords(path: str) -> np.ndarray:
    src = str(path).strip()
    if (not src) or (not os.path.exists(src)):
        return np.zeros((0, 3), dtype=np.float32)
    ca: List[List[float]] = []
    xyz: List[List[float]] = []
    with open(src, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if not (line.startswith("ATOM") or line.startswith("HETATM")):
                continue
            try:
                x = float(line[30:38])
                y = float(line[38:46])
                z = float(line[46:54])
            except Exception:
                continue
            atom = str(line[12:16]).strip().upper()
            xyz.append([x, y, z])
            if atom == "CA":
                ca.append([x, y, z])
    use = ca if len(ca) > 0 else xyz
    if len(use) <= 0:
        return np.zeros((0, 3), dtype=np.float32)
    return np.asarray(use, dtype=np.float32)


def _load_protein_coords(target: str, native_path: str) -> np.ndarray:
    if str(native_path).strip() and os.path.exists(str(native_path)):
        arr = _parse_pdb_ca_or_atom_coords(str(native_path))
        if arr.shape[0] > 0:
            return arr
    c, _ = load_native_structure(str(target))
    if c is None:
        return np.zeros((0, 3), dtype=np.float32)
    arr = c.detach().cpu().numpy()
    if arr.ndim != 2 or arr.shape[1] != 3:
        return np.zeros((0, 3), dtype=np.float32)
    return arr.astype(np.float32, copy=False)


def _compose_ligand_xyz(row: Dict[str, Any]) -> np.ndarray:
    px = _safe_float(row.get("pocket_x", 0.0))
    py = _safe_float(row.get("pocket_y", 0.0))
    pz = _safe_float(row.get("pocket_z", 0.0))
    b0 = np.asarray(
        [
            _safe_float(row.get("ligand_bead0_x", -0.8)),
            _safe_float(row.get("ligand_bead0_y", 0.0)),
            _safe_float(row.get("ligand_bead0_z", 0.0)),
        ],
        dtype=np.float32,
    )
    b1 = np.asarray(
        [
            _safe_float(row.get("ligand_bead1_x", 0.8)),
            _safe_float(row.get("ligand_bead1_y", 0.0)),
            _safe_float(row.get("ligand_bead1_z", 0.0)),
        ],
        dtype=np.float32,
    )
    ctr = np.asarray([px, py, pz], dtype=np.float32)
    return np.stack([ctr + b0, ctr + b1], axis=0)


def _ligand_affinity_hint(row: Dict[str, Any]) -> float:
    mw = _safe_float(row.get("ligand_mw", 200.0))
    logp = _safe_float(row.get("ligand_logp", 1.0))
    rot = _safe_float(row.get("ligand_rot_bonds", 2.0))
    h_d = _safe_float(row.get("ligand_h_donors", 0.0))
    h_a = _safe_float(row.get("ligand_h_acceptors", 0.0))

    mw_n = min(max((mw - 120.0) / 500.0, 0.0), 1.0)
    logp_n = min(max((logp + 1.5) / 6.5, 0.0), 1.0)
    rot_n = min(max(rot / 12.0, 0.0), 1.0)
    polar_n = min(max((h_d + h_a) / 14.0, 0.0), 1.0)
    return float(0.35 * mw_n + 0.35 * logp_n + 0.15 * rot_n + 0.15 * polar_n)


def _to_atom_line(
    serial: int,
    atom_name: str,
    res_name: str,
    chain_id: str,
    res_seq: int,
    xyz: Sequence[float],
    element: str,
    hetatm: bool = False,
) -> str:
    rec = "HETATM" if bool(hetatm) else "ATOM  "
    x, y, z = float(xyz[0]), float(xyz[1]), float(xyz[2])
    return (
        f"{rec}{serial:5d} {atom_name:<4s}{res_name:>3s} {chain_id:1s}{res_seq:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}{1.00:6.2f}{30.0:6.2f}          {element:>2s}"
    )


def _write_frame_pdb(path: str, protein_ca: np.ndarray, ligand_xyz: np.ndarray, frame_idx: int) -> None:
    lines: List[str] = [f"REMARK LIGAND_TRAJECTORY_FRAME {int(frame_idx)}"]
    serial = 1
    for i in range(int(protein_ca.shape[0])):
        lines.append(_to_atom_line(serial, "CA", "GLY", "A", i + 1, protein_ca[i], "C", hetatm=False))
        serial += 1
    lines.append("TER")
    for i in range(int(ligand_xyz.shape[0])):
        lines.append(_to_atom_line(serial, f"C{i+1}", "LIG", "L", 1, ligand_xyz[i], "C", hetatm=True))
        serial += 1
    lines.append("END")
    _ensure_dir(os.path.dirname(path) or ".")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def _simulate(
    protein: np.ndarray,
    ligand0: np.ndarray,
    pocket: np.ndarray,
    *,
    frames: int,
    step_size: float,
    noise_scale: float,
    pocket_attract: float,
    protein_repulse: float,
    bond_k: float,
    repulse_cutoff_A: float,
    max_pocket_radius_A: float,
    seed: int,
) -> List[np.ndarray]:
    lig = np.asarray(ligand0, dtype=np.float32).copy()
    prot = np.asarray(protein, dtype=np.float32)
    pctr = np.asarray(pocket, dtype=np.float32)
    rng = np.random.default_rng(int(seed))
    out: List[np.ndarray] = []

    nb = int(lig.shape[0])
    if nb <= 0:
        return out
    bond_ref = np.linalg.norm(lig[0] - lig[1]) if nb >= 2 else 0.0

    for _ in range(int(max(frames, 1))):
        center = np.mean(lig, axis=0)
        nxt = lig.copy()
        for i in range(nb):
            force = np.asarray(-(center - pctr) * float(pocket_attract), dtype=np.float32)
            if prot.size > 0:
                diff = lig[i][None, :] - prot
                dist = np.linalg.norm(diff, axis=1) + 1e-6
                mask = dist < float(repulse_cutoff_A)
                if np.any(mask):
                    unit = diff[mask] / dist[mask, None]
                    mag = float(protein_repulse) * (float(repulse_cutoff_A) - dist[mask]) / float(repulse_cutoff_A)
                    force += np.sum(unit * mag[:, None], axis=0) / max(1, int(np.sum(mask)))
            if nb >= 2:
                j = 1 - i
                vec = lig[i] - lig[j]
                d = float(np.linalg.norm(vec)) + 1e-6
                force += np.asarray(-float(bond_k) * (d - float(bond_ref)) * (vec / d), dtype=np.float32)
            noise = rng.normal(0.0, float(noise_scale), size=3).astype(np.float32)
            nxt[i] = lig[i] + float(step_size) * force + noise
        lig = nxt
        new_center = np.mean(lig, axis=0)
        radial = float(np.linalg.norm(new_center - pctr))
        if radial > float(max_pocket_radius_A):
            pull = (radial - float(max_pocket_radius_A)) / max(radial, 1e-6)
            lig -= (new_center - pctr)[None, :] * float(pull)
        out.append(lig.copy())
    return out


def run_batch(args: argparse.Namespace) -> Dict[str, Any]:
    queue_csv = str(args.queue_csv).strip()
    if (not queue_csv) or (not os.path.exists(queue_csv)):
        raise FileNotFoundError(f"queue csv not found: {queue_csv}")
    df = pd.read_csv(queue_csv)
    if df.empty:
        raise ValueError(f"queue csv is empty: {queue_csv}")
    max_jobs = int(args.max_jobs)
    if max_jobs > 0:
        df = df.head(max_jobs).copy()

    out_root = str(args.out_root).strip() or f"runs/ligand_traj_{dt.date.today().isoformat()}"
    _ensure_dir(out_root)

    rows: List[Dict[str, Any]] = []
    failed = 0
    for row in df.to_dict(orient="records"):
        queue_id = str(row.get("queue_id", "")).strip()
        if not queue_id:
            queue_id = f"{_slug(str(row.get('target','target')))}__rep{_safe_int(row.get('replica_idx', 0)):04d}"
        target = str(row.get("target", "unknown")).strip()
        ligand_id = str(row.get("ligand_id", "ligand")).strip()
        native_path = str(row.get(str(args.native_path_col), "")).strip()
        protein = _load_protein_coords(target=target, native_path=native_path)
        if protein.shape[0] <= 0 and bool(args.fail_on_missing_native):
            failed += 1
            rows.append(
                {
                    "queue_id": queue_id,
                    "target": target,
                    "ligand_id": ligand_id,
                    "status": "failed_missing_native",
                    "frames_written": 0,
                    "trajectory_dir": "",
                    "error": "native_structure_not_found",
                }
            )
            continue
        if protein.shape[0] <= 0:
            protein = np.zeros((1, 3), dtype=np.float32)

        ligand0 = _compose_ligand_xyz(row)
        pocket = np.asarray(
            [
                _safe_float(row.get("pocket_x", 0.0)),
                _safe_float(row.get("pocket_y", 0.0)),
                _safe_float(row.get("pocket_z", 0.0)),
            ],
            dtype=np.float32,
        )
        affinity = _ligand_affinity_hint(row)
        k_attr = float(args.pocket_attract_base) * (0.60 + 1.40 * affinity)
        noise_scale = float(args.noise_scale) * (1.20 - 0.70 * affinity)
        k_rep = float(args.protein_repulse) * (1.00 + 0.30 * max(0.0, 1.0 - affinity))

        sim_frames = _simulate(
            protein=protein,
            ligand0=ligand0,
            pocket=pocket,
            frames=int(args.frames),
            step_size=float(args.step_size),
            noise_scale=float(noise_scale),
            pocket_attract=float(k_attr),
            protein_repulse=float(k_rep),
            bond_k=float(args.bond_k),
            repulse_cutoff_A=float(args.repulse_cutoff_A),
            max_pocket_radius_A=float(args.max_pocket_radius_A),
            seed=int(args.seed) + abs(hash(queue_id)) % 1000003,
        )
        tdir = os.path.join(out_root, queue_id)
        _ensure_dir(tdir)
        stride = max(1, int(args.write_every))
        written = 0
        for idx, lig in enumerate(sim_frames):
            if idx % stride != 0:
                continue
            out_path = os.path.join(tdir, f"frame_{idx:05d}.pdb")
            _write_frame_pdb(out_path, protein_ca=protein, ligand_xyz=lig, frame_idx=idx)
            written += 1

        rows.append(
            {
                "queue_id": queue_id,
                "target": target,
                "ligand_id": ligand_id,
                "status": "ok",
                "frames_written": int(written),
                "trajectory_dir": tdir,
                "affinity_hint": float(affinity),
                "k_attr": float(k_attr),
                "noise_scale": float(noise_scale),
                "protein_repulse": float(k_rep),
                "error": "",
            }
        )

    out_df = pd.DataFrame(rows)
    out_manifest_csv = str(args.out_manifest_csv).strip() or f"{out_root}_manifest.csv"
    out_summary_json = str(args.out_summary_json).strip() or f"{out_root}_summary.json"
    out_summary_md = str(args.out_summary_md).strip() or f"{out_root}_summary.md"
    _ensure_dir(os.path.dirname(out_manifest_csv) or ".")
    out_df.to_csv(out_manifest_csv, index=False)

    ok_df = out_df[out_df["status"] == "ok"].copy() if (not out_df.empty and "status" in out_df.columns) else pd.DataFrame()
    summary = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "queue_rows": int(len(df)),
        "processed_rows": int(len(out_df)),
        "ok_rows": int(len(ok_df)),
        "failed_rows": int(failed),
        "frames_requested": int(args.frames),
        "min_frames_written": int(ok_df["frames_written"].min()) if (not ok_df.empty) else 0,
        "mean_frames_written": float(ok_df["frames_written"].mean()) if (not ok_df.empty) else 0.0,
        "out_root": os.path.abspath(out_root),
        "artifacts": {
            "manifest_csv": out_manifest_csv,
            "summary_json": out_summary_json,
            "summary_md": out_summary_md,
        },
    }
    with open(out_summary_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    lines = [
        "# Ligand Trajectory Batch",
        "",
        f"- generated_at_local: {summary['generated_at_local']}",
        f"- queue_rows: {summary['queue_rows']}",
        f"- processed_rows: {summary['processed_rows']}",
        f"- ok_rows: {summary['ok_rows']}",
        f"- failed_rows: {summary['failed_rows']}",
        f"- frames_requested: {summary['frames_requested']}",
        f"- min_frames_written: {summary['min_frames_written']}",
        f"- mean_frames_written: {summary['mean_frames_written']}",
        f"- out_root: `{out_root}`",
        f"- manifest_csv: `{out_manifest_csv}`",
    ]
    with open(out_summary_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return summary


def build_parser() -> argparse.ArgumentParser:
    stamp = dt.date.today().isoformat()
    p = argparse.ArgumentParser(
        description=(
            "Generate coarse-grained ligand-protein trajectory frames per queue job. "
            "Outputs one frame PDB sequence per queue_id directory."
        )
    )
    p.add_argument("--queue-csv", type=str, required=True)
    p.add_argument("--out-root", type=str, default=f"runs/ligand_traj_{stamp}")
    p.add_argument("--frames", type=int, default=120)
    p.add_argument("--write-every", type=int, default=1)
    p.add_argument("--max-jobs", type=int, default=0)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--step-size", type=float, default=0.04)
    p.add_argument("--noise-scale", type=float, default=0.15)
    p.add_argument("--pocket-attract-base", type=float, default=0.16)
    p.add_argument("--protein-repulse", type=float, default=0.22)
    p.add_argument("--bond-k", type=float, default=0.25)
    p.add_argument("--repulse-cutoff-A", type=float, default=4.5)
    p.add_argument("--max-pocket-radius-A", type=float, default=12.0)
    p.add_argument("--native-path-col", type=str, default="native_pdb_path")
    p.add_argument("--fail-on-missing-native", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--out-manifest-csv", type=str, default="")
    p.add_argument("--out-summary-json", type=str, default="")
    p.add_argument("--out-summary-md", type=str, default="")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = run_batch(args)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
