#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _ca_atoms(path: Path, chain_id: str) -> dict[tuple[str, str, str], np.ndarray]:
    atoms: dict[tuple[str, str, str], np.ndarray] = {}
    if not path.exists():
        return atoms
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if not line.startswith("ATOM"):
                continue
            if line[12:16].strip() != "CA":
                continue
            chain = (line[21:22].strip() or "_")
            if chain != chain_id:
                continue
            key = (chain, line[22:27].strip(), line[17:20].strip())
            try:
                atoms[key] = np.array(
                    [float(line[30:38]), float(line[38:46]), float(line[46:54])],
                    dtype=float,
                )
            except ValueError:
                continue
    return atoms


def _kabsch(moving: np.ndarray, reference: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    moving_center = moving.mean(axis=0)
    reference_center = reference.mean(axis=0)
    moving_zero = moving - moving_center
    reference_zero = reference - reference_center
    covariance = moving_zero.T @ reference_zero
    v, _s, wt = np.linalg.svd(covariance)
    sign = np.sign(np.linalg.det(v @ wt))
    rotation = v @ np.diag([1.0, 1.0, sign]) @ wt
    translation = reference_center - moving_center @ rotation
    return rotation, translation


def _rmsd(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) == 0 or len(b) == 0:
        return math.inf
    return float(np.sqrt(np.mean(np.sum((a - b) ** 2, axis=1))))


def _case_result(case_dir: Path, *, acceptable_ligand_rmsd_a: float, receptor_chain: str, ligand_chain: str) -> dict[str, Any]:
    complex_id = case_dir.name
    receptor_unbound = case_dir / f"{complex_id}_r_u.pdb"
    ligand_unbound = case_dir / f"{complex_id}_l_u.pdb"
    reference = case_dir / f"{complex_id}_target.pdb"
    if not reference.exists():
        reference = case_dir / f"{complex_id}_reference.pdb"
    blockers: list[str] = []
    for path, blocker in [
        (receptor_unbound, "receptor_unbound_pdb_missing"),
        (ligand_unbound, "ligand_unbound_pdb_missing"),
        (reference, "reference_complex_pdb_missing"),
    ]:
        if not path.exists():
            blockers.append(blocker)

    receptor_ca = _ca_atoms(receptor_unbound, receptor_chain)
    reference_receptor_ca = _ca_atoms(reference, receptor_chain)
    ligand_ca = _ca_atoms(ligand_unbound, ligand_chain)
    reference_ligand_ca = _ca_atoms(reference, ligand_chain)
    receptor_keys = sorted(set(receptor_ca) & set(reference_receptor_ca))
    ligand_keys = sorted(set(ligand_ca) & set(reference_ligand_ca))
    if len(receptor_keys) < 3:
        blockers.append("matched_receptor_ca_below_minimum")
    if len(ligand_keys) < 3:
        blockers.append("matched_ligand_ca_below_minimum")

    receptor_rmsd = math.inf
    ligand_rmsd = math.inf
    dockq_proxy = 0.0
    acceptable = False
    if not blockers:
        moving_receptor = np.stack([receptor_ca[key] for key in receptor_keys])
        reference_receptor = np.stack([reference_receptor_ca[key] for key in receptor_keys])
        rotation, translation = _kabsch(moving_receptor, reference_receptor)
        aligned_receptor = moving_receptor @ rotation + translation
        moving_ligand = np.stack([ligand_ca[key] for key in ligand_keys])
        reference_ligand = np.stack([reference_ligand_ca[key] for key in ligand_keys])
        aligned_ligand = moving_ligand @ rotation + translation
        receptor_rmsd = _rmsd(aligned_receptor, reference_receptor)
        ligand_rmsd = _rmsd(aligned_ligand, reference_ligand)
        dockq_proxy = 1.0 / (1.0 + (ligand_rmsd / float(acceptable_ligand_rmsd_a)) ** 2)
        acceptable = ligand_rmsd <= float(acceptable_ligand_rmsd_a)

    return {
        "suite_id": "protein_protein_docking_benchmark_v5",
        "complex_id": complex_id,
        "result_status": "pass" if acceptable and not blockers else "fail",
        "dockq_acceptable": int(bool(acceptable and not blockers)),
        "dockq_proxy": dockq_proxy,
        "ligand_ca_rmsd_A": ligand_rmsd if math.isfinite(ligand_rmsd) else "",
        "receptor_ca_rmsd_A": receptor_rmsd if math.isfinite(receptor_rmsd) else "",
        "matched_receptor_ca_count": len(receptor_keys),
        "matched_ligand_ca_count": len(ligand_keys),
        "receptor_unbound_pdb": str(receptor_unbound),
        "ligand_unbound_pdb": str(ligand_unbound),
        "reference_complex_pdb": str(reference),
        "blocker_count": len(blockers),
        "blockers": ";".join(blockers),
    }


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def build_results(args: argparse.Namespace) -> dict[str, Any]:
    dataset = _resolve(args.dataset_artifact)
    ready_dir = dataset / "HADDOCK-ready"
    case_dirs = sorted(path for path in ready_dir.iterdir() if path.is_dir()) if ready_dir.exists() else []
    if int(args.max_complexes) > 0:
        case_dirs = case_dirs[: int(args.max_complexes)]
    rows = [
        _case_result(
            case_dir,
            acceptable_ligand_rmsd_a=float(args.acceptable_ligand_rmsd_a),
            receptor_chain=_text(args.receptor_chain) or "A",
            ligand_chain=_text(args.ligand_chain) or "B",
        )
        for case_dir in case_dirs
    ]
    acceptable_count = sum(1 for row in rows if _float(row.get("dockq_acceptable")) == 1.0)
    acceptable_rate = acceptable_count / len(rows) if rows else 0.0
    threshold = float(args.threshold)
    blockers: list[str] = []
    if not dataset.exists():
        blockers.append("dataset_artifact_missing")
    if not ready_dir.exists():
        blockers.append("haddock_ready_dir_missing")
    if not rows:
        blockers.append("complex_triplets_missing")
    if acceptable_rate + 1e-12 < threshold:
        blockers.append("dockq_acceptable_rate_below_threshold")
    fields = [
        "suite_id",
        "complex_id",
        "result_status",
        "dockq_acceptable",
        "dockq_proxy",
        "ligand_ca_rmsd_A",
        "receptor_ca_rmsd_A",
        "matched_receptor_ca_count",
        "matched_ligand_ca_count",
        "receptor_unbound_pdb",
        "ligand_unbound_pdb",
        "reference_complex_pdb",
        "blocker_count",
        "blockers",
    ]
    out_csv = _resolve(args.out_csv)
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    _write_csv(out_csv, rows, fields)
    summary = {
        "packet_type": "bm5_complex_proxy_results",
        "suite_id": "protein_protein_docking_benchmark_v5",
        "status": "bm5_complex_proxy_results_ready" if not blockers else "blocked_bm5_complex_proxy_results",
        "pass": not blockers,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "dataset_artifact": str(dataset),
        "haddock_ready_dir": str(ready_dir),
        "complex_count": len(rows),
        "dockq_acceptable_count": acceptable_count,
        "dockq_acceptable_rate": acceptable_rate,
        "primary_metric": "dockq_acceptable_rate",
        "primary_metric_value": acceptable_rate,
        "primary_metric_threshold": threshold,
        "acceptable_ligand_rmsd_A": float(args.acceptable_ligand_rmsd_a),
        "out_csv": str(out_csv),
        "external_state_mutated": False,
        "download_executed": False,
        "prediction_generation_enabled": False,
        "claim_boundary": (
            "BM5 protein-complex proxy adapter only; it aligns unbound receptor CA atoms to the released reference "
            "complex and reports ligand CA RMSD/acceptable-rate as a local DockQ-style regression proxy. It does not "
            "run HADDOCK, use external SaaS, submit targets, download data, or claim official blind protein-protein "
            "docking performance."
        ),
        "next_required_step": (
            "Fingerprint this result CSV, build the suite scorecard, then refresh public benchmark gates."
            if not blockers
            else "Repair BM5 local triplets or complex-pose adapter performance, then rebuild these results."
        ),
    }
    payload = {"summary": summary, "rows": rows[:20]}
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(
        "\n".join(
            [
                "# BM5 Complex Proxy Results",
                "",
                f"- status: `{summary['status']}`",
                f"- complex_count: `{summary['complex_count']}`",
                f"- dockq_acceptable_rate: `{summary['dockq_acceptable_rate']}`",
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
    parser = argparse.ArgumentParser(description="Build BM5 local protein-complex DockQ-style proxy results.")
    parser.add_argument("--dataset-artifact", default="data/public_benchmarks/protein_protein_docking_benchmark_v5")
    parser.add_argument("--max-complexes", type=int, default=0)
    parser.add_argument("--threshold", type=float, default=0.2)
    parser.add_argument("--acceptable-ligand-rmsd-a", type=float, default=10.0)
    parser.add_argument("--receptor-chain", default="A")
    parser.add_argument("--ligand-chain", default="B")
    parser.add_argument("--out-csv", default="runs/protein_protein_docking_benchmark_v5_benchmark_results_current.csv")
    parser.add_argument("--out-json", default="runs/protein_protein_docking_benchmark_v5_results_current.json")
    parser.add_argument("--out-md", default="runs/protein_protein_docking_benchmark_v5_results_current.md")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    build_results(parse_args(argv))


if __name__ == "__main__":
    main()
