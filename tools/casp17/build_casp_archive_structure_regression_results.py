#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from betelgeuze_product.structure_analysis import analyze_structure_source

ROOT = Path(__file__).resolve().parents[2]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _target_id(path: Path) -> str:
    return path.stem


def build_results(args: argparse.Namespace) -> dict[str, Any]:
    dataset = _resolve(args.dataset_artifact)
    out_csv = _resolve(args.out_csv)
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    pdbs = sorted(dataset.rglob("*.pdb"))
    if int(args.max_targets) > 0:
        pdbs = pdbs[: int(args.max_targets)]

    rows: list[dict[str, Any]] = []
    for pdb in pdbs:
        analysis = analyze_structure_source({"pdb_path": str(pdb)}, root=ROOT)
        parsed = analysis.get("status") == "structure_analysis_ready" and _int(analysis.get("atom_count")) > 0
        rows.append(
            {
                "suite_id": "casp_archive_structure_regression",
                "target_id": _target_id(pdb),
                "pdb_path": str(pdb),
                "analysis_status": _text(analysis.get("status")),
                "pass": int(bool(parsed)),
                "atom_count": _int(analysis.get("atom_count")),
                "chain_count": _int(analysis.get("chain_count")),
                "residue_count": _int(analysis.get("residue_count")),
                "polymer_residue_count": _int(analysis.get("polymer_residue_count")),
                "ligand_like_residue_count": _int(analysis.get("ligand_like_residue_count")),
                "blocker_count": _int(analysis.get("blocker_count")),
            }
        )

    pass_count = sum(1 for row in rows if _int(row.get("pass")) == 1)
    target_pass_rate = pass_count / len(rows) if rows else 0.0
    blockers: list[str] = []
    if not dataset.exists():
        blockers.append("dataset_artifact_missing")
    if not rows:
        blockers.append("casp_archive_pdb_targets_missing")
    if target_pass_rate + 1e-12 < float(args.threshold):
        blockers.append("target_pass_rate_below_threshold")

    fields = [
        "suite_id",
        "target_id",
        "pdb_path",
        "analysis_status",
        "pass",
        "atom_count",
        "chain_count",
        "residue_count",
        "polymer_residue_count",
        "ligand_like_residue_count",
        "blocker_count",
    ]
    _write_csv(out_csv, rows, fields)
    summary = {
        "packet_type": "casp_archive_structure_regression_results",
        "suite_id": "casp_archive_structure_regression",
        "status": "casp_archive_structure_regression_results_ready" if not blockers else "blocked_casp_archive_structure_regression_results",
        "pass": not blockers,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "dataset_artifact": str(dataset),
        "dataset_artifact_present": dataset.exists(),
        "target_count": len(rows),
        "target_pass_count": pass_count,
        "target_pass_rate": target_pass_rate,
        "primary_metric": "target_pass_rate",
        "primary_metric_value": target_pass_rate,
        "primary_metric_threshold": float(args.threshold),
        "out_csv": str(out_csv),
        "external_state_mutated": False,
        "docking_results_emitted": False,
        "prediction_generation_enabled": False,
        "claim_boundary": (
            "CASP archive structure-regression adapter only; it batch-parses released local CASP target PDB files "
            "with the product structure-analysis engine and reports parser/readiness pass rate. It does not predict "
            "new structures, compute official CASP native-accuracy metrics, submit to CASP, download data, or claim "
            "strict-blind performance."
        ),
        "next_required_step": (
            "Fingerprint this result CSV, build the suite scorecard, then refresh public benchmark gates."
            if not blockers
            else "Repair local CASP archive extraction or structure parser failures, then rebuild these results."
        ),
    }
    payload = {"summary": summary, "rows": rows[:20]}
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(
        "\n".join(
            [
                "# CASP Archive Structure Regression Results",
                "",
                f"- status: `{summary['status']}`",
                f"- target_count: `{summary['target_count']}`",
                f"- target_pass_count: `{summary['target_pass_count']}`",
                f"- target_pass_rate: `{summary['target_pass_rate']}`",
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
    parser = argparse.ArgumentParser(description="Build product structure-analysis regression results for local CASP archive PDBs.")
    parser.add_argument("--dataset-artifact", default="data/public_benchmarks/casp_archive_structure_regression")
    parser.add_argument("--max-targets", type=int, default=0)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--out-csv", default="runs/casp_archive_structure_regression_benchmark_results_current.csv")
    parser.add_argument("--out-json", default="runs/casp_archive_structure_regression_results_current.json")
    parser.add_argument("--out-md", default="runs/casp_archive_structure_regression_results_current.md")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    build_results(parse_args(argv))


if __name__ == "__main__":
    main()
