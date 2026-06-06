#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return int(default)


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        x = float(v)
        if x != x:
            return float(default)
        return x
    except Exception:
        return float(default)


def _read_binder_pairs(path: str) -> set[Tuple[str, str]]:
    out: set[Tuple[str, str]] = set()
    src = str(path).strip()
    if (not src) or (not os.path.isfile(src)):
        return out
    try:
        with open(src, "r", encoding="utf-8", errors="ignore") as f:
            r = csv.DictReader(f)
            for row in r:
                if not isinstance(row, dict):
                    continue
                is_binder = _safe_int(row.get("is_binder", 0), 0)
                if is_binder <= 0:
                    continue
                t = str(row.get("target", "")).strip()
                lid = str(row.get("ligand_id", "")).strip()
                if t and lid:
                    out.add((t, lid))
    except Exception:
        return out
    return out


def _load_queue_rows(path: str) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        r = csv.DictReader(f)
        for row in r:
            if isinstance(row, dict):
                rows.append({str(k): str(v) for k, v in row.items()})
    return rows


def _balanced_pick(rows: List[Dict[str, str]], max_jobs: int, binder_pairs: set[Tuple[str, str]]) -> List[Dict[str, str]]:
    if max_jobs <= 0:
        return []
    # Prefer binders first, then fill with decoys while balancing targets.
    with_key: List[Tuple[Dict[str, str], bool]] = []
    for row in rows:
        t = str(row.get("target", "")).strip()
        lid = str(row.get("ligand_id", "")).strip()
        is_binder = (t, lid) in binder_pairs if binder_pairs else False
        with_key.append((row, is_binder))
    with_key.sort(key=lambda x: (not x[1], str(x[0].get("target", "")), str(x[0].get("queue_id", ""))))

    picked: List[Dict[str, str]] = []
    per_target: Dict[str, int] = {}
    for row, _ in with_key:
        if len(picked) >= max_jobs:
            break
        target = str(row.get("target", "")).strip() or "unknown"
        cur = per_target.get(target, 0)
        min_seen = min(per_target.values()) if per_target else 0
        # Keep simple per-target balancing without expensive sorting loops.
        if cur > min_seen + 2:
            continue
        picked.append(row)
        per_target[target] = cur + 1
    if len(picked) < max_jobs:
        seen = {str(r.get("queue_id", "")) for r in picked}
        for row, _ in with_key:
            qid = str(row.get("queue_id", ""))
            if qid in seen:
                continue
            picked.append(row)
            if len(picked) >= max_jobs:
                break
    return picked[:max_jobs]


def _write_pdb(path: str, target: str, ligand_id: str, protein_ca: np.ndarray, ligand_xyz: np.ndarray) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    lines: List[str] = []
    lines.append(f"REMARK TARGET {target}")
    lines.append(f"REMARK LIGAND {ligand_id}")
    serial = 1
    for i in range(int(protein_ca.shape[0])):
        x, y, z = protein_ca[i]
        lines.append(
            "ATOM  {serial:5d}  CA  ALA A{resi:4d}    {x:8.3f}{y:8.3f}{z:8.3f}"
            "{occ:6.2f}{bf:6.2f}          C ".format(
                serial=serial,
                resi=(i + 1),
                x=float(x),
                y=float(y),
                z=float(z),
                occ=1.00,
                bf=20.00,
            )
        )
        serial += 1
    lines.append("TER")
    for j in range(int(ligand_xyz.shape[0])):
        x, y, z = ligand_xyz[j]
        atom_name = f"C{j + 1}"
        lines.append(
            "HETATM{serial:5d} {atom_name:<4s} LIG L{resi:4d}    {x:8.3f}{y:8.3f}{z:8.3f}"
            "{occ:6.2f}{bf:6.2f}          C ".format(
                serial=serial,
                atom_name=atom_name,
                resi=1,
                x=float(x),
                y=float(y),
                z=float(z),
                occ=1.00,
                bf=10.00,
            )
        )
        serial += 1
    lines.append("END")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def _compute_min_distance(protein_ca: np.ndarray, ligand_frames: np.ndarray) -> float:
    if protein_ca.ndim != 2 or ligand_frames.ndim != 3:
        return 0.0
    if protein_ca.shape[0] <= 0 or ligand_frames.shape[0] <= 0:
        return 0.0
    # Keep memory bounded: compute on final frame and every 8th frame.
    idx = list(range(0, int(ligand_frames.shape[0]), 8))
    if idx[-1] != int(ligand_frames.shape[0]) - 1:
        idx.append(int(ligand_frames.shape[0]) - 1)
    mins: List[float] = []
    for i in idx:
        lig = ligand_frames[i]  # [B,3]
        diff = protein_ca[:, None, :] - lig[None, :, :]
        d2 = np.sum(diff * diff, axis=2)
        mins.append(float(np.sqrt(np.min(d2))))
    return float(min(mins)) if mins else 0.0


def _run_cmd(cmd: List[str]) -> Dict[str, Any]:
    proc = subprocess.run(cmd, text=True, capture_output=True)
    return {
        "cmd": cmd,
        "returncode": int(proc.returncode),
        "ok": bool(proc.returncode == 0),
        "stdout_tail": "\n".join((proc.stdout or "").splitlines()[-40:]),
        "stderr_tail": "\n".join((proc.stderr or "").splitlines()[-40:]),
    }


def run(args: argparse.Namespace) -> Dict[str, Any]:
    run_prefix = str(args.run_prefix).strip()
    if not run_prefix:
        raise ValueError("--run-prefix is required")

    queue_csv = str(args.queue_csv).strip() or f"{run_prefix}_stage1_queue.csv"
    stage2_dir = str(args.stage2_dir).strip() or f"{run_prefix}_stage2_traj_frames"
    labels_csv = str(args.labels_csv).strip()
    out_prefix = str(args.out_prefix).strip() or f"{run_prefix}_stage2_visual"
    out_csv = f"{out_prefix}_rows.csv"
    out_json = f"{out_prefix}_summary.json"
    out_html = f"{out_prefix}_dashboard.html"
    out_dashboard_json = f"{out_prefix}_dashboard.json"
    out_pdb_dir = f"{out_prefix}_pdb"

    if (not os.path.isfile(queue_csv)) or (not os.path.isdir(stage2_dir)):
        payload = {
            "ok": False,
            "error": "missing_inputs",
            "queue_csv": queue_csv,
            "stage2_dir": stage2_dir,
        }
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        return payload

    binder_pairs = _read_binder_pairs(labels_csv)
    queue_rows = _load_queue_rows(queue_csv)
    npz_paths = sorted(glob.glob(os.path.join(stage2_dir, "*", "trajectory_ligand.npz")))
    npz_paths.extend(sorted(glob.glob(os.path.join(stage2_dir, "*.npz"))))
    npz_paths.extend(sorted(glob.glob(os.path.join(stage2_dir, "*", "*.npz"))))
    available_qids = set()
    for p in npz_paths:
        base = os.path.basename(p)
        if base == "trajectory_ligand.npz":
            available_qids.add(os.path.basename(os.path.dirname(p)))
        elif base.lower().endswith(".npz"):
            available_qids.add(os.path.splitext(base)[0])
    available_rows = [r for r in queue_rows if str(r.get("queue_id", "")).strip() in available_qids]
    selected = _balanced_pick(available_rows, int(max(1, args.max_jobs * 3)), binder_pairs)

    emitted_rows: List[Dict[str, Any]] = []
    missing_npz = 0
    for row in selected:
        if len(emitted_rows) >= int(args.max_jobs):
            break
        qid = str(row.get("queue_id", "")).strip()
        target = str(row.get("target", "")).strip()
        ligand_id = str(row.get("ligand_id", "")).strip()
        if not qid:
            continue
        npz_path = os.path.join(stage2_dir, qid, "trajectory_ligand.npz")
        if not os.path.isfile(npz_path):
            npz_path = os.path.join(stage2_dir, f"{qid}.npz")
        if not os.path.isfile(npz_path):
            shard_hits = sorted(glob.glob(os.path.join(stage2_dir, "*", f"{qid}.npz")))
            npz_path = shard_hits[0] if shard_hits else ""
        if not npz_path or not os.path.isfile(npz_path):
            missing_npz += 1
            continue
        try:
            z = np.load(npz_path, allow_pickle=False)
            protein_ca = np.asarray(z["protein_ca"], dtype=np.float32)
            ligand_frames = np.asarray(z["ligand_frames"], dtype=np.float32)
        except Exception:
            continue
        if protein_ca.ndim != 2 or ligand_frames.ndim != 3:
            continue
        if ligand_frames.shape[0] <= 0:
            continue
        ligand_last = ligand_frames[-1]
        pdb_path = os.path.join(out_pdb_dir, f"{qid}.pdb")
        _write_pdb(pdb_path, target=target, ligand_id=ligand_id, protein_ca=protein_ca, ligand_xyz=ligand_last)
        min_dist = _compute_min_distance(protein_ca, ligand_frames)
        emitted_rows.append(
            {
                "queue_id": qid,
                "target": target,
                "ligand_id": ligand_id,
                "trajectory_frames": int(ligand_frames.shape[0]),
                "ligand_bead_count": int(ligand_frames.shape[1]),
                "mean_min_distance_A": float(min_dist),
                "trajectory_npz": npz_path,
                "backmapped_pdb": pdb_path,
            }
        )

    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "queue_id",
                "target",
                "ligand_id",
                "trajectory_frames",
                "ligand_bead_count",
                "mean_min_distance_A",
                "trajectory_npz",
                "backmapped_pdb",
            ],
        )
        w.writeheader()
        for r in emitted_rows:
            w.writerow(r)

    dash_rec: Dict[str, Any] = {
        "cmd": [],
        "returncode": 0,
        "ok": True,
        "stdout_tail": "",
        "stderr_tail": "",
    }
    if emitted_rows:
        dash_cmd: List[str] = [
            sys.executable,
            "tools/visualize_experiment_dashboard.py",
            "--csv",
            out_csv,
            "--metrics",
            "mean_min_distance_A,trajectory_frames,ligand_bead_count",
            "--max-metrics",
            "3",
            "--max-rows",
            str(int(max(32, args.max_jobs))),
            "--target-col",
            "target",
            "--title",
            f"Ligand Stage2 Visual Snapshot ({os.path.basename(run_prefix)})",
            "--out-html",
            out_html,
            "--out-json",
            out_dashboard_json,
            "--pdb-glob",
            os.path.join(out_pdb_dir, "*.pdb"),
            "--max-pdb",
            str(int(args.max_jobs)),
            "--viewer-engine",
            str(args.viewer_engine),
        ]
        dash_rec = _run_cmd(dash_cmd)

    payload = {
        "ok": bool(len(emitted_rows) > 0 and dash_rec.get("ok", False)),
        "run_prefix": run_prefix,
        "queue_csv": queue_csv,
        "stage2_dir": stage2_dir,
        "labels_csv": labels_csv,
        "max_jobs": int(args.max_jobs),
        "selected_rows": int(len(selected)),
        "available_stage2_rows": int(len(available_rows)),
        "visual_rows": int(len(emitted_rows)),
        "missing_npz_count": int(missing_npz),
        "artifacts": {
            "rows_csv": out_csv,
            "summary_json": out_json,
            "dashboard_html": out_html,
            "dashboard_json": out_dashboard_json,
            "pdb_dir": out_pdb_dir,
        },
        "dashboard": dash_rec,
    }
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return payload


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Build non-intrusive stage2 visual snapshot for ligand HTVS run.")
    p.add_argument("--run-prefix", type=str, required=True)
    p.add_argument("--queue-csv", type=str, default="")
    p.add_argument("--stage2-dir", type=str, default="")
    p.add_argument("--labels-csv", type=str, default="")
    p.add_argument("--max-jobs", type=int, default=24)
    p.add_argument("--viewer-engine", type=str, choices=["auto", "3dmol", "molstar"], default="auto")
    p.add_argument("--out-prefix", type=str, default="")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    run(args)


if __name__ == "__main__":
    main()
