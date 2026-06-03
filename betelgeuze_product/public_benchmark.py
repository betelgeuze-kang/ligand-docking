from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

CLAIM_BOUNDARY = (
    "Product public benchmark contract only; it defines reproducible public benchmark suites and validates "
    "operator-provided scorecard rows. It does not download datasets, run docking, compute metrics, register servers, "
    "submit predictions, send email, choose licenses, or mutate external state."
)

REQUIRED_SCORECARD_FIELDS = (
    "suite_id",
    "benchmark_family",
    "dataset_source_url",
    "scorecard_json",
    "status",
    "primary_metric",
    "primary_metric_value",
    "primary_metric_threshold",
    "regression_baseline_ref",
    "run_command",
)

BENCHMARK_SUITES = (
    {
        "suite_id": "lit_pcba_virtual_screening",
        "benchmark_family": "protein_ligand_virtual_screening",
        "dataset_source_url": "https://zenodo.org/records/4588239",
        "scope": "Experimental active/inactive virtual-screening benchmark for enrichment, ROC-AUC, PR-AUC, and EF metrics.",
        "release_role": "primary_ligand_screening_gate",
        "primary_metric": "EF1",
        "primary_metric_threshold": 1.2,
        "required_for_commercial_release": True,
    },
    {
        "suite_id": "dude_z_decoy_smoke",
        "benchmark_family": "protein_ligand_decoy_screening",
        "dataset_source_url": "https://dude.docking.org/",
        "scope": "Docking active/decoy smoke and regression benchmark; use as bias-aware guardrail, not sole product proof.",
        "release_role": "decoy_bias_guardrail",
        "primary_metric": "ROC_AUC",
        "primary_metric_threshold": 0.6,
        "required_for_commercial_release": True,
    },
    {
        "suite_id": "pdbbind_casf_pose_affinity",
        "benchmark_family": "protein_ligand_pose_affinity",
        "dataset_source_url": "https://www.pdbbind-plus.org.cn/",
        "scope": "Pose recovery, scoring, ranking, and affinity regression on curated protein-ligand complexes.",
        "release_role": "pose_affinity_gate",
        "primary_metric": "pose_success_rate",
        "primary_metric_threshold": 0.35,
        "required_for_commercial_release": True,
    },
    {
        "suite_id": "protein_protein_docking_benchmark_v5",
        "benchmark_family": "protein_complex_docking",
        "dataset_source_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC4677049/",
        "scope": "Protein-protein/complex docking benchmark with DockQ-style acceptable/medium/high-quality categories.",
        "release_role": "complex_docking_gate",
        "primary_metric": "dockq_acceptable_rate",
        "primary_metric_threshold": 0.2,
        "required_for_commercial_release": True,
    },
    {
        "suite_id": "casp_archive_structure_regression",
        "benchmark_family": "structure_prediction_regression",
        "dataset_source_url": "https://predictioncenter.org/",
        "scope": "Historical CASP/CASP17 archive targets for structure-analysis regression without live server registration.",
        "release_role": "structure_prediction_regression_gate",
        "primary_metric": "target_pass_rate",
        "primary_metric_threshold": 0.5,
        "required_for_commercial_release": True,
    },
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _read_scorecard_rows(path: str | Path) -> tuple[bool, list[dict[str, str]]]:
    scorecard_path = Path(path)
    if not scorecard_path.exists():
        return False, []
    with scorecard_path.open("r", encoding="utf-8", newline="") as handle:
        return True, [{str(k): _text(v) for k, v in row.items()} for row in csv.DictReader(handle)]


def _row(
    suite: dict[str, Any],
    evidence: dict[str, str] | None,
    *,
    scorecard_csv_present: bool,
) -> dict[str, Any]:
    status = _text(evidence.get("status") if evidence else "")
    scorecard_json = _text(evidence.get("scorecard_json") if evidence else "")
    dataset_source_url = _text(evidence.get("dataset_source_url") if evidence else "")
    primary_metric = _text(evidence.get("primary_metric") if evidence else "") or _text(suite["primary_metric"])
    metric_value = _float(evidence.get("primary_metric_value") if evidence else None)
    metric_threshold = _float(evidence.get("primary_metric_threshold") if evidence else suite["primary_metric_threshold"])
    run_command = _text(evidence.get("run_command") if evidence else "")
    baseline = _text(evidence.get("regression_baseline_ref") if evidence else "")
    missing_fields = [
        field
        for field in REQUIRED_SCORECARD_FIELDS
        if not _text(evidence.get(field) if evidence else "")
    ]
    source_matches = dataset_source_url == _text(suite["dataset_source_url"])
    metric_pass = status == "pass" and metric_value >= metric_threshold
    evidence_ready = (
        scorecard_csv_present
        and evidence is not None
        and not missing_fields
        and source_matches
        and bool(scorecard_json)
        and bool(run_command)
        and bool(baseline)
        and metric_pass
    )
    blockers: list[str] = []
    if not scorecard_csv_present:
        blockers.append("scorecard_csv_missing")
    if evidence is None:
        blockers.append("scorecard_row_missing")
    if missing_fields:
        blockers.append("missing_fields=" + ";".join(missing_fields))
    if evidence is not None and not source_matches:
        blockers.append("dataset_source_url_mismatch")
    if evidence is not None and status != "pass":
        blockers.append("scorecard_status_not_pass")
    if evidence is not None and metric_value < metric_threshold:
        blockers.append("primary_metric_below_threshold")

    return {
        "suite_id": _text(suite["suite_id"]),
        "benchmark_family": _text(suite["benchmark_family"]),
        "release_role": _text(suite["release_role"]),
        "status": "ready" if evidence_ready else "blocked",
        "required_for_commercial_release": bool(suite["required_for_commercial_release"] is True),
        "dataset_source_url": _text(suite["dataset_source_url"]),
        "scope": _text(suite["scope"]),
        "primary_metric": primary_metric,
        "primary_metric_value": metric_value,
        "primary_metric_threshold": metric_threshold,
        "scorecard_json": scorecard_json,
        "regression_baseline_ref": baseline,
        "run_command": run_command,
        "blockers": ",".join(blockers),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
    }


def build_product_public_benchmark_contract(*, scorecard_csv: str | Path) -> dict[str, Any]:
    scorecard_csv_present, scorecard_rows = _read_scorecard_rows(scorecard_csv)
    evidence_by_suite = {_text(row.get("suite_id")): row for row in scorecard_rows}
    rows = [
        _row(suite, evidence_by_suite.get(_text(suite["suite_id"])), scorecard_csv_present=scorecard_csv_present)
        for suite in BENCHMARK_SUITES
    ]
    required_rows = [row for row in rows if row["required_for_commercial_release"]]
    ready_required_rows = [row for row in required_rows if row["status"] == "ready"]
    blocked_rows = [row for row in rows if row["status"] != "ready"]
    duplicate_count = max(0, len(scorecard_rows) - len(evidence_by_suite))
    unknown_suite_count = sum(1 for row in scorecard_rows if _text(row.get("suite_id")) not in {_text(s["suite_id"]) for s in BENCHMARK_SUITES})
    contract_ready = (
        scorecard_csv_present
        and not blocked_rows
        and duplicate_count == 0
        and unknown_suite_count == 0
        and len(ready_required_rows) == len(required_rows)
    )
    blockers = [
        {
            "code": f"{row['suite_id']}_not_ready",
            "severity": "hard",
            "suite_id": row["suite_id"],
            "reason": f"{row['scope']} Blockers: {row['blockers'] or 'none'}.",
        }
        for row in blocked_rows
    ]
    if duplicate_count:
        blockers.append(
            {
                "code": "duplicate_scorecard_rows",
                "severity": "hard",
                "suite_id": "",
                "reason": f"Scorecard intake has {duplicate_count} duplicate suite rows.",
            }
        )
    if unknown_suite_count:
        blockers.append(
            {
                "code": "unknown_scorecard_suites",
                "severity": "hard",
                "suite_id": "",
                "reason": f"Scorecard intake has {unknown_suite_count} rows for suites outside the product benchmark contract.",
            }
        )
    summary = {
        "packet_type": "product_public_benchmark_contract",
        "status": "product_public_benchmark_contract_ready" if contract_ready else "blocked_product_public_benchmark_contract",
        "public_benchmark_validation_ready": contract_ready,
        "scorecard_csv": str(scorecard_csv),
        "scorecard_csv_present": scorecard_csv_present,
        "suite_count": len(rows),
        "required_suite_count": len(required_rows),
        "ready_required_suite_count": len(ready_required_rows),
        "blocked_suite_count": len(blocked_rows),
        "duplicate_scorecard_row_count": duplicate_count,
        "unknown_suite_count": unknown_suite_count,
        "benchmark_mode": "self_hosted_reproducible_public_benchmarks",
        "requires_institution_registration": False,
        "requires_24h_server": False,
        "requires_competition_season": False,
        "requires_paid_vps": False,
        "external_state_mutated": False,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Use the benchmark scorecard rows as release performance evidence."
            if contract_ready
            else "Materialize public benchmark datasets, run suite-specific scorecards, and fill the scorecard intake CSV."
        ),
    }
    return {"summary": summary, "blockers": blockers, "rows": rows}
