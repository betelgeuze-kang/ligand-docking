from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from betelgeuze_product.public_benchmark import BENCHMARK_SUITES

CLAIM_BOUNDARY = (
    "Public benchmark result provenance only; it fingerprints an existing product-engine benchmark result artifact "
    "and optional execution summary. It does not download datasets, run docking, compute benchmark metrics, submit "
    "predictions, send email, or mutate external state outside requested output artifacts."
)
GOLD_EXECUTION_SUMMARY_FIELDS = (
    "gold_metric_schema_version",
    "gold_metric_status",
    "gold_metric_blockers",
    "top1_mean_rmsd_A",
    "top5_best_mean_rmsd_A",
    "top1_pose_success_rate",
    "top5_pose_success_rate",
    "ranking_spearman",
    "pr_auc",
    "topk_hit_rate",
    "decoy_rejection_rate",
    "baseline_ranking_spearman",
    "refine_ranking_spearman_delta",
    "refine_improvement_observed",
    "heldout_complex_count",
    "chirality_failure_rate",
    "tautomer_failure_rate",
    "protonation_failure_rate",
    "chemistry_evidence_coverage",
    "abstention_precision",
    "mean_runtime_ms",
    "peak_memory_mb",
    "subset_identity_sha256",
)
PDBBIND_CASF_SUITE_ID = "pdbbind_casf_pose_affinity"
PDBBIND_CASF_DEFAULT_EXECUTION_SUMMARY = "pdbbind_casf_pose_affinity_results_current.json"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _suite_by_id(suite_id: str) -> dict[str, Any] | None:
    wanted = _text(suite_id)
    return next((suite for suite in BENCHMARK_SUITES if _text(suite.get("suite_id")) == wanted), None)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _csv_row_count(path: Path) -> int:
    if not path.exists() or path.is_dir() or path.suffix.lower() != ".csv":
        return 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def _csv_columns(path: Path) -> list[str]:
    if not path.exists() or path.is_dir() or path.suffix.lower() != ".csv":
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or [])


def _read_summary(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    summary = payload.get("summary") if isinstance(payload, dict) else payload
    if summary is None and isinstance(payload, dict):
        summary = payload
    return summary if isinstance(summary, dict) else {}


def _execution_summary_path(suite_id: str, result_artifact: Path, execution_summary_json: str | Path) -> Path | None:
    if _text(execution_summary_json):
        return Path(execution_summary_json)
    if _text(suite_id) == PDBBIND_CASF_SUITE_ID:
        return result_artifact.parent / PDBBIND_CASF_DEFAULT_EXECUTION_SUMMARY
    return None


def build_public_benchmark_result_provenance(
    *,
    suite_id: str,
    result_artifact: str | Path,
    execution_summary_json: str | Path = "",
    source_engine: str = "betelgeuze_product",
    min_result_rows: int = 1,
) -> dict[str, Any]:
    suite = _suite_by_id(suite_id)
    result = Path(result_artifact)
    execution_summary_path = _execution_summary_path(suite_id, result, execution_summary_json)
    execution_summary = _read_summary(execution_summary_path)
    result_present = result.exists() and result.is_file()
    result_rows = _csv_row_count(result)
    result_columns = _csv_columns(result)
    result_sha256 = _sha256(result) if result_present else ""
    blockers: list[str] = []

    if suite is None:
        blockers.append("suite_id_unknown")
        benchmark_family = ""
        dataset_source_url = ""
    else:
        benchmark_family = _text(suite.get("benchmark_family"))
        dataset_source_url = _text(suite.get("dataset_source_url"))
    if not result_present:
        blockers.append("result_artifact_missing")
    if result_rows < int(min_result_rows):
        blockers.append("result_rows_below_minimum")
    if _text(source_engine) not in {"betelgeuze_product", "betelgeuze_ligand_htvs"}:
        blockers.append("source_engine_invalid")
    if execution_summary_path and not execution_summary:
        blockers.append("execution_summary_unreadable")
    if execution_summary and execution_summary.get("pass") is not True:
        blockers.append("execution_summary_not_pass")

    product_engine_result = not blockers
    summary = {
        "packet_type": "public_benchmark_result_provenance",
        "suite_id": _text(suite_id),
        "status": "public_benchmark_result_provenance_ready" if product_engine_result else "blocked_public_benchmark_result_provenance",
        "product_engine_result": product_engine_result,
        "blocker_count": len(sorted(set(blockers))),
        "blockers": sorted(set(blockers)),
        "benchmark_family": benchmark_family,
        "dataset_source_url": dataset_source_url,
        "source_engine": _text(source_engine),
        "result_artifact": str(result),
        "result_artifact_present": result_present,
        "result_artifact_sha256": result_sha256,
        "result_row_count": result_rows,
        "result_columns": result_columns,
        "min_result_rows": int(min_result_rows),
        "execution_summary_json": str(execution_summary_path) if execution_summary_path else "",
        "execution_summary_present": bool(execution_summary),
        "execution_summary_pass": bool(execution_summary.get("pass") is True) if execution_summary else False,
        "external_state_mutated": False,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Use this provenance JSON with the suite scorecard adapter."
            if product_engine_result
            else "Generate product-engine benchmark results, then rebuild this provenance artifact."
        ),
    }
    for field in GOLD_EXECUTION_SUMMARY_FIELDS:
        if field in execution_summary:
            summary[field] = execution_summary[field]
    rows = [
        {
            "check": "result_artifact_present",
            "status": "pass" if result_present else "fail",
            "observed": str(result),
            "required": "existing product-engine benchmark result CSV",
        },
        {
            "check": "result_rows_minimum",
            "status": "pass" if result_rows >= int(min_result_rows) else "fail",
            "observed": str(result_rows),
            "required": str(int(min_result_rows)),
        },
        {
            "check": "source_engine",
            "status": "pass" if _text(source_engine) in {"betelgeuze_product", "betelgeuze_ligand_htvs"} else "fail",
            "observed": _text(source_engine),
            "required": "betelgeuze_product or betelgeuze_ligand_htvs",
        },
    ]
    return {"summary": summary, "rows": rows}


def write_provenance(path: str | Path, payload: dict[str, Any]) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
