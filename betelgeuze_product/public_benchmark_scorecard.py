from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from betelgeuze_product.public_benchmark import BENCHMARK_SUITES

CLAIM_BOUNDARY = (
    "Public benchmark suite scorecard adapter only; it validates an operator-provided benchmark metric and emits the "
    "standard product public benchmark scorecard row. It does not download datasets, run docking, compute metrics, "
    "register servers, submit predictions, send email, or mutate external state outside requested output artifacts."
)

PDBBIND_CASF_SUITE_ID = "pdbbind_casf_pose_affinity"
PDBBIND_CASF_REQUIRED_GOLD_FIELDS = (
    "gold_metric_schema_version",
    "gold_metric_status",
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
PDBBIND_CASF_REQUIRED_RESULT_COLUMNS = (
    "active_label",
    "affinity_label",
    "score",
    "baseline_score",
    "split_id",
    "abstained",
    "chirality_failure",
    "tautomer_failure",
    "protonation_failure",
    "chemistry_evidence_present",
    "runtime_ms",
    "peak_memory_mb",
    "pose_rmsd_method",
    "pose_rmsd_diagnostics",
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _suite_by_id(suite_id: str) -> dict[str, Any] | None:
    wanted = _text(suite_id)
    return next((suite for suite in BENCHMARK_SUITES if _text(suite.get("suite_id")) == wanted), None)


def _scorecard_row(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "suite_id": summary.get("suite_id", ""),
        "benchmark_family": summary.get("benchmark_family", ""),
        "dataset_source_url": summary.get("dataset_source_url", ""),
        "scorecard_json": summary.get("scorecard_json", ""),
        "product_provenance_json": summary.get("product_provenance_json", ""),
        "status": "pass" if summary.get("status") == "public_benchmark_suite_scorecard_pass" else "fail",
        "primary_metric": summary.get("primary_metric", ""),
        "primary_metric_value": summary.get("primary_metric_value", 0.0),
        "primary_metric_threshold": summary.get("primary_metric_threshold", 0.0),
        "regression_baseline_ref": summary.get("regression_baseline_ref", ""),
        "run_command": summary.get("run_command", ""),
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_provenance(path: Path | None) -> tuple[bool, dict[str, Any]]:
    if path is None or not path.exists():
        return False, {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return True, {}
    summary = payload.get("summary") if isinstance(payload, dict) else {}
    return True, summary if isinstance(summary, dict) else {}


def _pdbbind_casf_gold_metric_blockers(provenance: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if _text(provenance.get("gold_metric_schema_version")) != "tier_beta_docking_gold_metrics_v1":
        blockers.append("pdbbind_casf_gold_metric_schema_missing")
    if _text(provenance.get("gold_metric_status")) != "pass":
        blockers.append("pdbbind_casf_gold_metric_status_not_pass")
    for field in PDBBIND_CASF_REQUIRED_GOLD_FIELDS:
        value = provenance.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            blockers.append(f"pdbbind_casf_gold_metric_field_missing:{field}")
    if provenance.get("refine_improvement_observed") is not True:
        blockers.append("pdbbind_casf_refine_improvement_not_observed")
    if _int(provenance.get("heldout_complex_count")) <= 0:
        blockers.append("pdbbind_casf_heldout_complex_count_missing")
    result_columns = provenance.get("result_columns") or []
    result_column_set = {_text(column) for column in result_columns if _text(column)}
    missing_columns = [
        column
        for column in PDBBIND_CASF_REQUIRED_RESULT_COLUMNS
        if column not in result_column_set
    ]
    if missing_columns:
        blockers.append("pdbbind_casf_result_columns_missing:" + ";".join(missing_columns))
    gold_blockers = provenance.get("gold_metric_blockers") or []
    if isinstance(gold_blockers, list) and gold_blockers:
        blockers.append("pdbbind_casf_gold_metric_blockers_present")
    return blockers


def build_public_benchmark_suite_scorecard(
    *,
    suite_id: str,
    primary_metric_value: float,
    out_json: str | Path,
    evidence_artifact: str | Path = "",
    product_provenance_json: str | Path = "",
    regression_baseline_ref: str = "",
    run_command: str = "",
    min_evidence_rows: int = 1,
    evidence_row_count: int = 0,
    primary_metric_name: str = "",
    primary_metric_threshold: float | None = None,
) -> dict[str, Any]:
    suite = _suite_by_id(suite_id)
    blockers: list[str] = []
    if suite is None:
        blockers.append("suite_id_unknown")
        family = ""
        source_url = ""
        metric_name = _text(primary_metric_name)
        threshold = _float(primary_metric_threshold)
    else:
        family = _text(suite["benchmark_family"])
        source_url = _text(suite["dataset_source_url"])
        metric_name = _text(primary_metric_name) or _text(suite["primary_metric"])
        threshold = _float(primary_metric_threshold if primary_metric_threshold is not None else suite["primary_metric_threshold"])
        if metric_name != _text(suite["primary_metric"]):
            blockers.append("primary_metric_mismatch")

    evidence_path = Path(evidence_artifact) if _text(evidence_artifact) else None
    evidence_present = evidence_path.exists() if evidence_path else False
    provenance_path = Path(product_provenance_json) if _text(product_provenance_json) else None
    provenance_present, provenance = _read_provenance(provenance_path)
    metric_value = _float(primary_metric_value)
    rows = _int(evidence_row_count)
    metric_gap = metric_value - threshold
    evidence_artifact_text = str(evidence_artifact) if _text(evidence_artifact) else ""
    provenance_text = str(product_provenance_json) if _text(product_provenance_json) else ""
    evidence_sha256 = _sha256(evidence_path) if evidence_path and evidence_present and evidence_path.is_file() else ""
    if not _text(regression_baseline_ref):
        blockers.append("regression_baseline_ref_missing")
    if not _text(run_command):
        blockers.append("run_command_missing")
    if evidence_path and not evidence_present:
        blockers.append("evidence_artifact_missing")
    if not evidence_path:
        blockers.append("evidence_artifact_not_declared")
    if rows < int(min_evidence_rows):
        blockers.append("evidence_rows_below_minimum")
    if metric_value + 1e-12 < threshold:
        blockers.append("primary_metric_below_threshold")
    if not provenance_path:
        blockers.append("product_provenance_json_not_declared")
    elif not provenance_present:
        blockers.append("product_provenance_json_missing")
    elif not provenance:
        blockers.append("product_provenance_json_invalid")
    else:
        if _text(provenance.get("suite_id")) != _text(suite_id):
            blockers.append("product_provenance_suite_id_mismatch")
        if provenance.get("product_engine_result") is not True:
            blockers.append("product_provenance_not_product_engine_result")
        if _text(provenance.get("source_engine")) not in {"betelgeuze_product", "betelgeuze_ligand_htvs"}:
            blockers.append("product_provenance_source_engine_invalid")
        if _text(provenance.get("result_artifact")) != evidence_artifact_text:
            blockers.append("product_provenance_result_artifact_mismatch")
        if evidence_sha256 and _text(provenance.get("result_artifact_sha256")) != evidence_sha256:
            blockers.append("product_provenance_result_sha256_mismatch")
        if _int(provenance.get("result_row_count")) < int(min_evidence_rows):
            blockers.append("product_provenance_rows_below_minimum")
        if _text(suite_id) == PDBBIND_CASF_SUITE_ID:
            blockers.extend(_pdbbind_casf_gold_metric_blockers(provenance))

    status = "public_benchmark_suite_scorecard_pass" if not blockers else "blocked_public_benchmark_suite_scorecard"
    blocker_text = ",".join(sorted(set(blockers)))
    summary = {
        "packet_type": "public_benchmark_suite_scorecard",
        "suite_id": _text(suite_id),
        "status": status,
        "pass": status == "public_benchmark_suite_scorecard_pass",
        "blocker_count": len(blockers),
        "blockers": sorted(set(blockers)),
        "benchmark_family": family,
        "dataset_source_url": source_url,
        "scorecard_json": str(out_json),
        "evidence_artifact": evidence_artifact_text,
        "evidence_artifact_present": evidence_present,
        "evidence_artifact_sha256": evidence_sha256,
        "product_provenance_json": provenance_text,
        "product_provenance_json_present": provenance_present,
        "product_provenance_source_engine": _text(provenance.get("source_engine")),
        "product_provenance_result_artifact": _text(provenance.get("result_artifact")),
        "product_provenance_result_artifact_sha256": _text(provenance.get("result_artifact_sha256")),
        "product_provenance_result_row_count": _int(provenance.get("result_row_count")),
        "operator_input_artifacts": ";".join(value for value in [evidence_artifact_text, provenance_text] if value),
        "operator_output_artifacts": str(out_json),
        "missing_input_artifacts": ";".join(
            value
            for value, missing in [
                (evidence_artifact_text, bool(evidence_path and not evidence_present)),
                (provenance_text, bool(provenance_path and not provenance_present)),
            ]
            if value and missing
        ),
        "evidence_row_count": rows,
        "min_evidence_rows": int(min_evidence_rows),
        "primary_metric": metric_name,
        "primary_metric_value": metric_value,
        "primary_metric_threshold": threshold,
        "threshold": threshold,
        "metric_gap_to_threshold": metric_gap,
        "regression_baseline_ref": _text(regression_baseline_ref),
        "run_command": _text(run_command),
        "blocker": blocker_text,
        "external_state_mutated": False,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Append this scorecard row to the product public benchmark scorecard intake CSV."
            if status == "public_benchmark_suite_scorecard_pass"
            else "Provide product-engine benchmark evidence, provenance, baseline reference, run command, and a metric value above threshold."
        ),
    }
    return {"summary": summary, "scorecard_row": _scorecard_row(summary)}


def write_scorecard(path: str | Path, payload: dict[str, Any]) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
