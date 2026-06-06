#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import pickle
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _text(value: Any) -> str:
    return str(value or "").strip()


def _coords(mol: Any) -> list[tuple[float, float, float]]:
    conformer = mol.GetConformer()
    coords: list[tuple[float, float, float]] = []
    for atom in mol.GetAtoms():
        if atom.GetAtomicNum() == 1:
            continue
        point = conformer.GetAtomPosition(atom.GetIdx())
        coords.append((float(point.x), float(point.y), float(point.z)))
    return coords


def _direct_rmsd(a: list[tuple[float, float, float]], b: list[tuple[float, float, float]]) -> float | None:
    if not a or len(a) != len(b):
        return None
    total = 0.0
    for (ax, ay, az), (bx, by, bz) in zip(a, b):
        total += (ax - bx) ** 2 + (ay - by) ** 2 + (az - bz) ** 2
    return math.sqrt(total / len(a))


def _load_ligand(path: Path) -> Any:
    payload = pickle.loads(path.read_bytes())
    if isinstance(payload, tuple) and payload:
        return payload[0]
    return payload


def _reference_path(data_dir: Path, complex_id: str) -> Path | None:
    for candidate in [data_dir / complex_id, data_dir / f"{complex_id}_ligand"]:
        if candidate.exists():
            return candidate
    return None


def _is_pose_file(path: Path) -> bool:
    name = path.name
    if name.endswith("_ligand"):
        return False
    if "_" not in name:
        return False
    suffix = name.rsplit("_", 1)[-1]
    return suffix.isdigit()


def build_results(args: argparse.Namespace) -> dict[str, Any]:
    dataset = _resolve(args.dataset_artifact)
    data_dir = dataset / "data_5_sdf"
    pose_files = sorted(path for path in data_dir.iterdir() if path.is_file() and _is_pose_file(path)) if data_dir.exists() else []
    if int(args.max_poses) > 0:
        pose_files = pose_files[: int(args.max_poses)]
    rows: list[dict[str, Any]] = []
    threshold = float(args.pose_success_rmsd_a)

    for pose_path in pose_files:
        complex_id = pose_path.name.split("_", 1)[0]
        reference = _reference_path(data_dir, complex_id)
        blockers: list[str] = []
        rmsd: float | None = None
        ref_atom_count = 0
        pose_atom_count = 0
        if reference is None:
            blockers.append("reference_ligand_missing")
        else:
            try:
                ref_coords = _coords(_load_ligand(reference))
                pose_coords = _coords(_load_ligand(pose_path))
                ref_atom_count = len(ref_coords)
                pose_atom_count = len(pose_coords)
                rmsd = _direct_rmsd(ref_coords, pose_coords)
                if rmsd is None:
                    blockers.append("heavy_atom_count_mismatch")
            except Exception as exc:  # noqa: BLE001 - artifact parser should report concrete row-level failure.
                blockers.append(f"rdkit_pickle_parse_failed:{type(exc).__name__}")
        success = rmsd is not None and rmsd <= threshold and not blockers
        rows.append(
            {
                "suite_id": "pdbbind_casf_pose_affinity",
                "complex_id": complex_id,
                "pose_id": pose_path.name,
                "pose_success": int(success),
                "pose_rmsd_A": rmsd if rmsd is not None else "",
                "pose_success_rmsd_threshold_A": threshold,
                "reference_ligand": str(reference or ""),
                "pose_artifact": str(pose_path),
                "reference_heavy_atom_count": ref_atom_count,
                "pose_heavy_atom_count": pose_atom_count,
                "blocker_count": len(blockers),
                "blockers": ";".join(blockers),
            }
        )

    scored_rows = [row for row in rows if _text(row.get("pose_rmsd_A"))]
    pose_success_count = sum(1 for row in rows if int(row.get("pose_success") or 0) == 1)
    pose_success_rate = pose_success_count / len(rows) if rows else 0.0
    by_complex: dict[str, list[float]] = {}
    for row in scored_rows:
        try:
            rmsd = float(row["pose_rmsd_A"])
        except (TypeError, ValueError):
            continue
        by_complex.setdefault(_text(row.get("complex_id")), []).append(rmsd)
    complex_success_count = sum(1 for values in by_complex.values() if min(values) <= threshold)
    complex_success_rate = complex_success_count / len(by_complex) if by_complex else 0.0
    primary_threshold = float(args.threshold)
    blockers: list[str] = []
    if not dataset.exists():
        blockers.append("dataset_artifact_missing")
    if not data_dir.exists():
        blockers.append("data_5_sdf_dir_missing")
    if not rows:
        blockers.append("pose_files_missing")
    if complex_success_rate + 1e-12 < primary_threshold:
        blockers.append("pose_success_rate_below_threshold")

    out_csv = _resolve(args.out_csv)
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    fields = [
        "suite_id",
        "complex_id",
        "pose_id",
        "pose_success",
        "pose_rmsd_A",
        "pose_success_rmsd_threshold_A",
        "reference_ligand",
        "pose_artifact",
        "reference_heavy_atom_count",
        "pose_heavy_atom_count",
        "blocker_count",
        "blockers",
    ]
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})

    summary = {
        "packet_type": "pdbbind_casf_pose_affinity_results",
        "suite_id": "pdbbind_casf_pose_affinity",
        "status": "pdbbind_casf_pose_affinity_results_ready" if not blockers else "blocked_pdbbind_casf_pose_affinity_results",
        "pass": not blockers,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "dataset_artifact": str(dataset),
        "data_5_sdf_dir": str(data_dir),
        "pose_count": len(rows),
        "scored_pose_count": len(scored_rows),
        "pose_success_count": pose_success_count,
        "pose_success_rate": complex_success_rate,
        "pose_row_success_rate": pose_success_rate,
        "complex_count": len(by_complex),
        "complex_pose_success_count": complex_success_count,
        "complex_pose_success_rate": complex_success_rate,
        "primary_metric": "pose_success_rate",
        "primary_metric_value": complex_success_rate,
        "primary_metric_threshold": primary_threshold,
        "pose_success_rmsd_threshold_A": threshold,
        "out_csv": str(out_csv),
        "external_state_mutated": False,
        "download_executed": False,
        "prediction_generation_enabled": False,
        "claim_boundary": (
            "PDBbind/CASF pose-affinity adapter only; it reads local RDKit-pickled CASF ligand/reference pose pairs "
            "and computes direct heavy-atom RMSD by preserved atom order. The primary pose_success_rate is aggregated "
            "per complex by best available pose, while pose_row_success_rate remains reported as a diagnostic. It does "
            "not run docking, train affinity models, use external SaaS, download data, or claim official CASF "
            "scoring/ranking performance."
        ),
        "next_required_step": (
            "Fingerprint this result CSV, build the suite scorecard, then refresh public benchmark gates."
            if rows
            else "Repair local CASF pose files, then rebuild these results."
        ),
    }
    payload = {"summary": summary, "rows": rows[:20]}
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(
        "\n".join(
            [
                "# PDBbind/CASF Pose Affinity Results",
                "",
                f"- status: `{summary['status']}`",
                f"- pose_count: `{summary['pose_count']}`",
                f"- pose_success_rate: `{summary['pose_success_rate']}`",
                f"- threshold: `{summary['primary_metric_threshold']}`",
                f"- out_csv: `{out_csv}`",
                "",
                "## Claim Boundary",
                "",
                summary["claim_boundary"],
                "",
            ]
        ),
        encoding="utf-8",
    )
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build PDBbind/CASF local pose RMSD proxy results from RDKit pickle files.")
    parser.add_argument("--dataset-artifact", default="data/public_benchmarks/pdbbind_casf_pose_affinity")
    parser.add_argument("--max-poses", type=int, default=0)
    parser.add_argument("--threshold", type=float, default=0.35)
    parser.add_argument("--pose-success-rmsd-a", type=float, default=2.0)
    parser.add_argument("--out-csv", default="runs/pdbbind_casf_pose_affinity_benchmark_results_current.csv")
    parser.add_argument("--out-json", default="runs/pdbbind_casf_pose_affinity_results_current.json")
    parser.add_argument("--out-md", default="runs/pdbbind_casf_pose_affinity_results_current.md")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    build_results(parse_args(argv))


if __name__ == "__main__":
    main()
