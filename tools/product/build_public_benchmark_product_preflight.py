#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import tarfile
from pathlib import Path
from typing import Any

from betelgeuze_product.public_benchmark import BENCHMARK_SUITES

ROOT = Path(__file__).resolve().parents[2]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _text(value: Any) -> str:
    return str(value or "").strip()


def _suite(suite_id: str) -> dict[str, Any]:
    return next((row for row in BENCHMARK_SUITES if _text(row.get("suite_id")) == _text(suite_id)), {})


def _tar_member_count(path: Path, limit: int = 10000) -> int:
    if not path.exists() or not path.is_file():
        return 0
    try:
        with tarfile.open(path) as tar:
            count = 0
            for _ in tar:
                count += 1
                if count >= limit:
                    break
            return count
    except tarfile.TarError:
        return 0


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path: Path, summary: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    lines = [
        "# Public Benchmark Product Preflight",
        "",
        f"- status: `{summary['status']}`",
        f"- suite_id: `{summary['suite_id']}`",
        f"- product_execution_ready: `{summary['product_execution_ready']}`",
        f"- blocker_count: `{summary['blocker_count']}`",
        f"- approval_token_required: `{summary['approval_token_required']}`",
        f"- dataset_artifact: `{summary['dataset_artifact']}`",
        f"- result_artifact: `{summary['result_artifact']}`",
        "",
        "## Blockers",
        "",
    ]
    blockers = summary.get("blockers") or []
    lines.extend([f"- `{blocker}`" for blocker in blockers] or ["- none"])
    lines.extend(["", "## Checks", "", "| check | status | observed | required |", "| --- | --- | --- | --- |"])
    for row in rows:
        lines.append(f"| `{row['check']}` | `{row['status']}` | `{row['observed']}` | `{row['required']}` |")
    lines.extend(["", "## Next Step", "", f"- {summary['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _default_dataset_artifact(suite_id: str) -> str:
    return f"data/public_benchmarks/{suite_id}"


def _default_result_artifact(suite_id: str) -> str:
    return f"runs/{suite_id}_benchmark_results_current.csv"


def _default_out_json(suite_id: str) -> str:
    return f"runs/{suite_id}_product_preflight_current.json"


def _default_out_md(suite_id: str) -> str:
    return f"runs/{suite_id}_product_preflight_current.md"


def _common_result_checks(result: Path, provenance: Path | None) -> tuple[list[str], list[dict[str, Any]]]:
    blockers: list[str] = []
    rows: list[dict[str, Any]] = []
    result_present = result.exists() and result.is_file()
    if not result_present:
        blockers.append("product_benchmark_result_artifact_missing")
    rows.append(
        {
            "check": "product_benchmark_result_artifact",
            "status": "pass" if result_present else "fail",
            "observed": str(result),
            "required": "existing product-engine benchmark result CSV",
        }
    )
    if provenance is not None:
        provenance_present = provenance.exists() and provenance.is_file()
        if not provenance_present:
            blockers.append("product_result_provenance_missing")
        rows.append(
            {
                "check": "product_result_provenance",
                "status": "pass" if provenance_present else "fail",
                "observed": str(provenance),
                "required": "existing product result provenance JSON",
            }
        )
    return blockers, rows


def _pdbbind_preflight(dataset: Path) -> tuple[list[str], list[dict[str, Any]], dict[str, Any]]:
    scoring_archive = dataset / "CASF-2016_scoring.tar.xz"
    docking_archive = dataset / "CASF-2016_docking.tar.xz"
    adapter = ROOT / "tools" / "build_pdbbind_casf_pose_affinity_results.py"
    scoring_members = _tar_member_count(scoring_archive, limit=1000)
    docking_members = _tar_member_count(docking_archive, limit=1000)
    extracted_dirs = [dataset / "CASF-2016_scoring", dataset / "CASF-2016_docking", dataset / "data_5_sdf"]
    blockers: list[str] = []
    if not scoring_archive.exists():
        blockers.append("pdbbind_casf_scoring_archive_missing")
    if not docking_archive.exists():
        blockers.append("pdbbind_casf_docking_archive_missing")
    if not any(path.exists() and path.is_dir() for path in extracted_dirs):
        blockers.append("pdbbind_casf_archives_not_extracted")
    if not adapter.exists():
        blockers.append("pdbbind_casf_product_pose_affinity_adapter_missing")
    rows = [
        {
            "check": "scoring_archive",
            "status": "pass" if scoring_archive.exists() else "fail",
            "observed": str(scoring_archive),
            "required": "CASF scoring archive staged locally",
        },
        {
            "check": "docking_archive",
            "status": "pass" if docking_archive.exists() else "fail",
            "observed": str(docking_archive),
            "required": "CASF docking archive staged locally",
        },
        {
            "check": "archive_member_probe",
            "status": "pass" if scoring_members > 0 and docking_members > 0 else "fail",
            "observed": f"scoring={scoring_members};docking={docking_members}",
            "required": "readable tar archives",
        },
        {
            "check": "pdbbind_casf_pose_affinity_adapter",
            "status": "pass" if adapter.exists() else "fail",
            "observed": str(adapter),
            "required": "local RDKit-pickle pose RMSD adapter",
        },
    ]
    return blockers, rows, {
        "scoring_archive_member_probe_count": scoring_members,
        "docking_archive_member_probe_count": docking_members,
        "adapter_path": str(adapter),
        "adapter_present": adapter.exists(),
    }


def _protein_protein_preflight(dataset: Path) -> tuple[list[str], list[dict[str, Any]], dict[str, Any]]:
    ready = dataset / "HADDOCK-ready"
    adapter = ROOT / "tools" / "build_bm5_complex_proxy_results.py"
    target_count = len(list(ready.glob("*/*_target.pdb"))) if ready.exists() else 0
    ligand_count = len(list(ready.glob("*/*_l_u.pdb"))) if ready.exists() else 0
    receptor_count = len(list(ready.glob("*/*_r_u.pdb"))) if ready.exists() else 0
    complete_triplets = min(target_count, ligand_count, receptor_count)
    blockers: list[str] = []
    if not ready.exists():
        blockers.append("protein_protein_haddock_ready_dir_missing")
    if complete_triplets <= 0:
        blockers.append("protein_protein_complex_triplets_missing")
    if not adapter.exists():
        blockers.append("protein_protein_product_complex_docking_adapter_missing")
    rows = [
        {
            "check": "haddock_ready_dir",
            "status": "pass" if ready.exists() else "fail",
            "observed": str(ready),
            "required": "BM5 HADDOCK-ready local directory",
        },
        {
            "check": "complex_triplet_probe",
            "status": "pass" if complete_triplets > 0 else "fail",
            "observed": str(complete_triplets),
            "required": "at least one target/l_u/r_u PDB triplet",
        },
        {
            "check": "protein_protein_complex_proxy_adapter",
            "status": "pass" if adapter.exists() else "fail",
            "observed": str(adapter),
            "required": "local BM5 complex-pose proxy adapter",
        },
    ]
    return blockers, rows, {
        "target_pdb_count": target_count,
        "ligand_unbound_pdb_count": ligand_count,
        "receptor_unbound_pdb_count": receptor_count,
        "complete_triplet_probe_count": complete_triplets,
        "adapter_path": str(adapter),
        "adapter_present": adapter.exists(),
    }


def _casp_preflight(dataset: Path) -> tuple[list[str], list[dict[str, Any]], dict[str, Any]]:
    archives = sorted(dataset.glob("*.tar.gz"))
    member_counts = {path.name: _tar_member_count(path, limit=1000) for path in archives}
    extracted_pdbs = list(dataset.rglob("*.pdb"))
    adapter = ROOT / "tools" / "casp17/build_casp_archive_structure_regression_results.py"
    blockers: list[str] = []
    if not archives:
        blockers.append("casp_archive_tarballs_missing")
    if not extracted_pdbs:
        blockers.append("casp_archive_targets_not_extracted")
    if not adapter.exists():
        blockers.append("casp_archive_structure_regression_adapter_missing")
    rows = [
        {
            "check": "casp_archive_tarballs",
            "status": "pass" if archives else "fail",
            "observed": str(len(archives)),
            "required": "one or more staged CASP archive tarballs",
        },
        {
            "check": "casp_archive_member_probe",
            "status": "pass" if any(count > 0 for count in member_counts.values()) else "fail",
            "observed": ";".join(f"{name}={count}" for name, count in member_counts.items()),
            "required": "readable target PDB archive members",
        },
        {
            "check": "casp_extracted_targets",
            "status": "pass" if extracted_pdbs else "fail",
            "observed": str(len(extracted_pdbs)),
            "required": "local extracted PDB targets for product structure-regression execution",
        },
        {
            "check": "casp_structure_regression_adapter",
            "status": "pass" if adapter.exists() else "fail",
            "observed": str(adapter),
            "required": "local product structure-analysis regression adapter",
        },
    ]
    return blockers, rows, {
        "archive_count": len(archives),
        "archive_member_probe_counts": member_counts,
        "extracted_pdb_count": len(extracted_pdbs),
        "adapter_path": str(adapter),
        "adapter_present": adapter.exists(),
    }


def build_preflight(args: argparse.Namespace) -> dict[str, Any]:
    suite_id = _text(args.suite_id)
    suite = _suite(suite_id)
    dataset = _resolve(args.dataset_artifact or _default_dataset_artifact(suite_id))
    result = _resolve(args.result_artifact or _default_result_artifact(suite_id))
    provenance = _resolve(args.product_provenance_json) if _text(args.product_provenance_json) else None
    blockers: list[str] = []
    rows: list[dict[str, Any]] = []
    details: dict[str, Any] = {}

    dataset_present = dataset.exists()
    if not suite:
        blockers.append("suite_id_unknown")
    if not dataset_present:
        blockers.append("dataset_artifact_missing")
    rows.append(
        {
            "check": "dataset_artifact",
            "status": "pass" if dataset_present else "fail",
            "observed": str(dataset),
            "required": _text(suite.get("dataset_source_url")) or "known public benchmark dataset",
        }
    )

    if suite_id == "pdbbind_casf_pose_affinity":
        suite_blockers, suite_rows, details = _pdbbind_preflight(dataset)
    elif suite_id == "protein_protein_docking_benchmark_v5":
        suite_blockers, suite_rows, details = _protein_protein_preflight(dataset)
    elif suite_id == "casp_archive_structure_regression":
        suite_blockers, suite_rows, details = _casp_preflight(dataset)
    else:
        suite_blockers, suite_rows, details = ["suite_product_preflight_not_implemented"], [], {}
    blockers.extend(suite_blockers)
    rows.extend(suite_rows)
    result_blockers, result_rows = _common_result_checks(result, provenance)
    blockers.extend(result_blockers)
    rows.extend(result_rows)

    blockers = sorted(set(blockers))
    product_execution_ready = dataset_present and not blockers
    approval_token = "APPROVE_PRODUCT_DOCKING_EXECUTION" if blockers else ""
    out_json = _resolve(args.out_json or _default_out_json(suite_id))
    out_md = _resolve(args.out_md or _default_out_md(suite_id))
    run_command = (
        f"python3 tools/build_public_benchmark_product_preflight.py --suite-id {suite_id} "
        f"--dataset-artifact {dataset} --result-artifact {result}"
    )
    summary = {
        "packet_type": "public_benchmark_product_preflight",
        "suite_id": suite_id,
        "status": "public_benchmark_product_preflight_ready" if product_execution_ready else "blocked_public_benchmark_product_preflight",
        "product_execution_ready": product_execution_ready,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "benchmark_family": _text(suite.get("benchmark_family")),
        "dataset_source_url": _text(suite.get("dataset_source_url")),
        "dataset_artifact": str(dataset),
        "dataset_artifact_present": dataset_present,
        "result_artifact": str(result),
        "result_artifact_present": result.exists() and result.is_file(),
        "product_provenance_json": str(provenance) if provenance else "",
        "approval_token_required": approval_token,
        "run_command": run_command,
        "external_state_mutated": False,
        "download_executed": False,
        "docking_results_emitted": False,
        "claim_boundary": (
            "Public benchmark product preflight only; it inspects staged local benchmark inputs and result/provenance "
            "artifacts. It does not extract archives, run docking, compute metrics, download, submit, or mutate external state."
        ),
        "next_required_step": (
            "Run product benchmark generation and scorecard commands."
            if product_execution_ready
            else "Resolve the listed local input/adapter/result blockers, then rebuild this preflight."
        ),
        **details,
    }
    payload = {"summary": summary, "rows": rows}
    _write_json(out_json, payload)
    _write_md(out_md, summary, rows)
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build read-only product-engine preflight for public benchmark suites.")
    parser.add_argument("--suite-id", required=True)
    parser.add_argument("--dataset-artifact", default="")
    parser.add_argument("--result-artifact", default="")
    parser.add_argument("--product-provenance-json", default="")
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    build_preflight(parse_args(argv))


if __name__ == "__main__":
    main()
