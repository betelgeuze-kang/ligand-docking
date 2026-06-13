#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from core.pocket_detection import detect_binding_pocket
from core.pose_generation import (
    POSE_CLAIM_BOUNDARY,
    cluster_poses_by_rmsd,
    generate_cross_docking_poses,
    generate_pose_ensemble,
)
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/product_pose_sampling_readiness_current.json"
DEFAULT_OUT_CSV = "runs/product_pose_sampling_readiness_current.csv"
DEFAULT_OUT_MD = "runs/product_pose_sampling_readiness_current.md"

CLAIM_BOUNDARY = (
    "Product pose sampling readiness only; it runs deterministic local pocket placement, multi-start conformer "
    "sampling, RMSD clustering, and bounded cross-docking/induced-fit guard smoke tests. It does not claim "
    "validated induced-fit, cross-target docking accuracy, pose RMSD parity, affinity ranking accuracy, run "
    "customer docking jobs, upload data, or mutate external state."
)

SYNTHETIC_PROTEIN_XYZ = np.asarray(
    [
        [-3.5, 0.0, 0.0],
        [-2.0, 2.5, 0.2],
        [0.5, 3.2, -0.1],
        [2.7, 1.4, 0.3],
        [3.4, -1.1, -0.2],
        [1.2, -3.1, 0.1],
        [-1.5, -3.0, -0.3],
        [-3.0, -1.2, 0.4],
        [0.0, 0.0, 4.2],
        [0.0, 0.0, -4.2],
    ],
    dtype=np.float32,
)

SYNTHETIC_HOLO_LIGAND_XYZ = np.asarray(
    [
        [-0.8, 0.0, 0.0],
        [0.8, 0.0, 0.0],
        [0.0, 1.1, 0.0],
    ],
    dtype=np.float32,
)

SYNTHETIC_POCKET_RESIDUE_ATOMS = [
    {"chain_id": "A", "resname": "SER", "residue_id": "101", "xyz": [-2.0, 2.5, 0.2]},
    {"chain_id": "A", "resname": "ASP", "residue_id": "102", "xyz": [2.7, 1.4, 0.3]},
    {"chain_id": "A", "resname": "PHE", "residue_id": "103", "xyz": [1.2, -3.1, 0.1]},
]


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _bool(value: Any) -> bool:
    return bool(value is True)


def _row(
    check_id: str,
    *,
    ready: bool,
    observed: str,
    required: str,
    evidence: str,
    claim_boundary: str = CLAIM_BOUNDARY,
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": "pass" if ready else "fail",
        "ready": ready,
        "observed": observed,
        "required": required,
        "evidence": evidence,
        "claim_boundary": claim_boundary,
        "release_blocker": not ready,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
    }


def _max_centroid_distance(poses: list[np.ndarray], center: np.ndarray) -> float:
    distances: list[float] = []
    for pose in poses:
        pts = np.asarray(pose, dtype=np.float32)
        if pts.size == 0:
            continue
        distances.append(float(np.linalg.norm(pts.mean(axis=0) - center.reshape(3))))
    return max(distances or [999.0])


def build_product_pose_sampling_readiness(
    *,
    smiles: str = "CCO",
    n_starts: int = 6,
    rmsd_cutoff_a: float = 0.35,
) -> dict[str, Any]:
    n_starts = max(int(n_starts), 1)
    pocket = detect_binding_pocket(SYNTHETIC_PROTEIN_XYZ, SYNTHETIC_HOLO_LIGAND_XYZ)
    pocket_center = np.asarray(pocket.get("pocket_center", [0.0, 0.0, 0.0]), dtype=np.float32)
    ensemble = generate_pose_ensemble(smiles, pocket_center, n_starts=n_starts, output_mode="2bead")
    poses = [np.asarray(pose, dtype=np.float32) for pose in ensemble.get("poses", [])]
    clusters = cluster_poses_by_rmsd(poses, rmsd_cutoff_a=float(rmsd_cutoff_a))
    cross = generate_cross_docking_poses(
        smiles,
        SYNTHETIC_PROTEIN_XYZ,
        holo_ligand_xyz=SYNTHETIC_HOLO_LIGAND_XYZ,
        n_starts=4,
        induced_fit=True,
        output_mode="2bead",
    )

    pose_count = int(ensemble.get("pose_count") or 0)
    cluster_count = int(clusters.get("cluster_count") or 0)
    cross_pose_count = len(cross.get("poses") or [])
    max_centroid_distance_a = _max_centroid_distance(poses, pocket_center)
    claim_boundary_guard_ready = (
        POSE_CLAIM_BOUNDARY in str(ensemble.get("claim_boundary") or "")
        and _bool(cross.get("induced_fit"))
        and str(cross.get("mode")) == "cross_docking"
    )
    centroid_bound_ready = max_centroid_distance_a <= 1.5

    rows = [
        _row(
            "ligand_guided_pocket_detection_ready",
            ready=str(pocket.get("status")) == "pocket_ready" and str(pocket.get("method")) == "ligand_guided",
            observed=(
                f"status={pocket.get('status')};method={pocket.get('method')};"
                f"shell_atoms={pocket.get('shell_atom_count')};contact_atoms={pocket.get('contact_atom_count')}"
            ),
            required="ligand-guided pocket detection returns pocket_ready with nonnegative local counts",
            evidence="core/pocket_detection.py",
        ),
        _row(
            "multi_start_pose_ensemble_ready",
            ready=str(ensemble.get("status")) == "pose_ensemble_ready" and pose_count >= n_starts,
            observed=f"status={ensemble.get('status')};pose_count={pose_count};requested={n_starts}",
            required="pose ensemble returns at least the requested deterministic multi-start pose count",
            evidence="core/pose_generation.py",
            claim_boundary=str(ensemble.get("claim_boundary") or POSE_CLAIM_BOUNDARY),
        ),
        _row(
            "pose_centroid_pocket_bound_ready",
            ready=centroid_bound_ready,
            observed=f"max_centroid_distance_a={max_centroid_distance_a:.4f}",
            required="generated local 2-bead pose centroids remain bound near the detected pocket center",
            evidence="core/pose_generation.py",
        ),
        _row(
            "pose_rmsd_diversity_surface_ready",
            ready=cluster_count >= 2 and len(clusters.get("assignments") or []) == pose_count,
            observed=f"cluster_count={cluster_count};assignment_count={len(clusters.get('assignments') or [])}",
            required="RMSD clustering exposes at least two pose-diversity clusters for the deterministic smoke",
            evidence="core/pose_generation.py",
        ),
        _row(
            "bounded_cross_docking_induced_fit_guard_ready",
            ready=(
                str(cross.get("status")) == "pose_ensemble_ready"
                and str(cross.get("mode")) == "cross_docking"
                and str(cross.get("pocket_method")) in {"ligand_guided", "grid_cavity", "protein_centroid_fallback"}
                and cross_pose_count == 4
            ),
            observed=(
                f"status={cross.get('status')};mode={cross.get('mode')};"
                f"pocket_method={cross.get('pocket_method')};pose_count={cross_pose_count};"
                f"induced_fit={cross.get('induced_fit')}"
            ),
            required="cross-docking smoke produces bounded local poses with induced-fit flag but no validated claim",
            evidence="core/pose_generation.py",
            claim_boundary=str(cross.get("claim_boundary") or POSE_CLAIM_BOUNDARY),
        ),
        _row(
            "pose_claim_boundary_guard_ready",
            ready=claim_boundary_guard_ready,
            observed=f"pose_claim_boundary={ensemble.get('claim_boundary')};cross_mode={cross.get('mode')}",
            required="pose/cross-docking outputs carry restricted claim boundary text",
            evidence="core/pose_generation.py",
            claim_boundary=POSE_CLAIM_BOUNDARY,
        ),
    ]
    blockers = [row for row in rows if row["status"] != "pass"]
    ready = not blockers
    summary = {
        "packet_type": "product_pose_sampling_readiness",
        "status": "product_pose_sampling_readiness_ready" if ready else "blocked_product_pose_sampling_readiness",
        "pose_sampling_readiness_ready": ready,
        "pose_generation_contract_ready": ready,
        "pocket_detection_ready": rows[0]["status"] == "pass",
        "multi_start_pose_ensemble_ready": rows[1]["status"] == "pass",
        "pose_centroid_pocket_bound_ready": rows[2]["status"] == "pass",
        "pose_rmsd_diversity_surface_ready": rows[3]["status"] == "pass",
        "bounded_cross_docking_induced_fit_guard_ready": rows[4]["status"] == "pass",
        "pose_claim_boundary_guard_ready": rows[5]["status"] == "pass",
        "check_count": len(rows),
        "pass_count": len(rows) - len(blockers),
        "blocker_count": len(blockers),
        "pose_count": pose_count,
        "requested_pose_start_count": n_starts,
        "cluster_count": cluster_count,
        "rmsd_cutoff_a": float(rmsd_cutoff_a),
        "cross_docking_pose_count": cross_pose_count,
        "pocket_method": str(pocket.get("method") or ""),
        "max_pose_centroid_distance_a": max_centroid_distance_a,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_grade_pose_accuracy_ready": False,
        "claim_grade_induced_fit_ready": False,
        "claim_grade_cross_docking_ready": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Pose sampling readiness is locally smoke-tested; keep pose accuracy, induced-fit, and cross-target "
            "claims blocked until curated public pose RMSD/LDDT-PLI/DockQ benchmark evidence clears."
            if ready
            else "Repair failed pose sampling checks before treating pose generation as a local product capability."
        ),
    }
    return {"summary": summary, "rows": rows, "blockers": blockers}


def _write_markdown(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    s = payload["summary"]
    lines = [
        "# Product Pose Sampling Readiness",
        "",
        f"- status: `{s['status']}`",
        f"- pose_sampling_readiness_ready: `{s['pose_sampling_readiness_ready']}`",
        f"- pass/check/blocker: `{s['pass_count']}/{s['check_count']}/{s['blocker_count']}`",
        f"- pose_count: `{s['pose_count']}`",
        f"- cluster_count: `{s['cluster_count']}`",
        f"- cross_docking_pose_count: `{s['cross_docking_pose_count']}`",
        f"- claim_grade_pose_accuracy_ready: `{s['claim_grade_pose_accuracy_ready']}`",
        "",
        "## Checks",
        "",
        "| check | status | observed | required |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(f"| `{row['check_id']}` | `{row['status']}` | `{row['observed']}` | {row['required']} |")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build product pose sampling readiness from deterministic local smoke checks.")
    parser.add_argument("--smiles", default="CCO")
    parser.add_argument("--n-starts", type=int, default=6)
    parser.add_argument("--rmsd-cutoff-a", type=float, default=0.35)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_product_pose_sampling_readiness(
        smiles=args.smiles,
        n_starts=args.n_starts,
        rmsd_cutoff_a=args.rmsd_cutoff_a,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
