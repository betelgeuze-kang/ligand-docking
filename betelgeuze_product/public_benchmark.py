from __future__ import annotations

import csv
import json
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


def _resolve_scorecard_json(path_like: str, *, root: Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _materialization_manifest_path(suite_id: str, *, root: Path) -> Path:
    stem = "lit_pcba" if suite_id == "lit_pcba_virtual_screening" else suite_id
    return root / "runs" / f"{stem}_materialization_manifest_current.json"


def _read_scorecard_summary(path_like: str, *, root: Path) -> tuple[bool, dict[str, Any]]:
    if not _text(path_like):
        return False, {}
    path = _resolve_scorecard_json(path_like, root=root)
    if not path.exists():
        return False, {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return True, {}
    summary = payload.get("summary") if isinstance(payload, dict) else {}
    return True, summary if isinstance(summary, dict) else {}


def _read_materialization_summary(suite_id: str, *, root: Path) -> tuple[Path, bool, dict[str, Any]]:
    path = _materialization_manifest_path(suite_id, root=root)
    if not path.exists():
        return path, False, {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return path, True, {}
    summary = payload.get("summary") if isinstance(payload, dict) else {}
    return path, True, summary if isinstance(summary, dict) else {}


def _materialization_operator_artifacts(summary: dict[str, Any]) -> tuple[list[str], list[str]]:
    if _text(summary.get("suite_id")) == "lit_pcba_virtual_screening":
        inputs = [
            summary.get("archive_path"),
            summary.get("extracted_dir"),
            summary.get("source_score_csv"),
            summary.get("source_label_csv"),
        ]
        outputs = [summary.get("out_scores_csv"), summary.get("out_labels_csv")]
    else:
        inputs = [summary.get("dataset_artifact")]
        outputs = [summary.get("result_artifact")]
    input_artifacts = [_text(value) for value in inputs if _text(value)]
    output_artifacts = [_text(value) for value in outputs if _text(value)]
    if not input_artifacts and _text(summary.get("dataset_artifact")):
        input_artifacts = [_text(summary.get("dataset_artifact"))]
    if not output_artifacts and _text(summary.get("result_artifact")):
        output_artifacts = [_text(summary.get("result_artifact"))]
    return input_artifacts, output_artifacts


def _row(
    suite: dict[str, Any],
    evidence: dict[str, str] | None,
    *,
    scorecard_csv_present: bool,
    root: Path,
) -> dict[str, Any]:
    status = _text(evidence.get("status") if evidence else "")
    scorecard_json = _text(evidence.get("scorecard_json") if evidence else "")
    dataset_source_url = _text(evidence.get("dataset_source_url") if evidence else "")
    primary_metric = _text(evidence.get("primary_metric") if evidence else "") or _text(suite["primary_metric"])
    metric_value = _float(evidence.get("primary_metric_value") if evidence else None)
    metric_threshold = _float(evidence.get("primary_metric_threshold") if evidence else suite["primary_metric_threshold"])
    run_command = _text(evidence.get("run_command") if evidence else "")
    baseline = _text(evidence.get("regression_baseline_ref") if evidence else "")
    scorecard_json_present, scorecard_summary = _read_scorecard_summary(scorecard_json, root=root)
    materialization_manifest, materialization_present, materialization_summary = _read_materialization_summary(
        _text(suite["suite_id"]),
        root=root,
    )
    scorecard_summary_suite_id = _text(scorecard_summary.get("suite_id"))
    scorecard_summary_status = _text(scorecard_summary.get("status"))
    scorecard_summary_pass = bool(scorecard_summary.get("pass") is True) or scorecard_summary_status.endswith("_pass")
    materialization_summary_suite_id = _text(materialization_summary.get("suite_id"))
    materialization_status = _text(materialization_summary.get("status"))
    materialization_ready = bool(materialization_summary.get("materialized") is True) and materialization_status.endswith(
        "_ready"
    )
    materialization_matches = materialization_summary_suite_id == _text(suite["suite_id"])
    materialization_blockers = materialization_summary.get("blockers") if isinstance(materialization_summary, dict) else []
    materialization_blocker_text = ";".join(_text(blocker) for blocker in materialization_blockers or [] if _text(blocker))
    materialization_run_command = _text(materialization_summary.get("run_command"))
    operator_input_artifacts, operator_output_artifacts = _materialization_operator_artifacts(materialization_summary)
    scorecard_run_command_template = _text(materialization_summary.get("scorecard_run_command_template"))
    missing_fields = [
        field
        for field in REQUIRED_SCORECARD_FIELDS
        if not _text(evidence.get(field) if evidence else "")
    ]
    source_matches = dataset_source_url == _text(suite["dataset_source_url"])
    metric_pass = status == "pass" and metric_value >= metric_threshold
    scorecard_json_matches = scorecard_summary_suite_id == _text(suite["suite_id"])
    scorecard_json_passes = scorecard_summary_pass and scorecard_summary_status not in {
        "blocked_lit_pcba_scorecard",
        "blocked_public_benchmark_suite_scorecard",
    }
    evidence_ready = (
        scorecard_csv_present
        and evidence is not None
        and not missing_fields
        and materialization_present
        and materialization_matches
        and materialization_ready
        and bool(materialization_run_command)
        and source_matches
        and scorecard_json_present
        and scorecard_json_matches
        and scorecard_json_passes
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
    if not materialization_present:
        blockers.append("materialization_manifest_missing")
    if materialization_present and not materialization_matches:
        blockers.append("materialization_manifest_suite_id_mismatch")
    if materialization_present and not materialization_ready:
        blockers.append("materialization_manifest_not_ready")
    if materialization_present and not materialization_run_command:
        blockers.append("materialization_run_command_missing")
    if evidence is not None and not source_matches:
        blockers.append("dataset_source_url_mismatch")
    if evidence is not None and not scorecard_json_present:
        blockers.append("scorecard_json_missing")
    if evidence is not None and scorecard_json_present and not scorecard_json_matches:
        blockers.append("scorecard_json_suite_id_mismatch")
    if evidence is not None and scorecard_json_present and not scorecard_json_passes:
        blockers.append("scorecard_json_status_not_pass")
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
        "scorecard_json_present": scorecard_json_present,
        "scorecard_json_summary_status": scorecard_summary_status,
        "materialization_manifest_json": str(materialization_manifest),
        "materialization_manifest_present": materialization_present,
        "materialization_manifest_status": materialization_status,
        "materialization_manifest_materialized": bool(materialization_summary.get("materialized") is True),
        "materialization_manifest_blockers": materialization_blocker_text,
        "materialization_run_command": materialization_run_command,
        "operator_input_artifacts": ";".join(operator_input_artifacts),
        "operator_output_artifacts": ";".join(operator_output_artifacts),
        "scorecard_run_command_template": scorecard_run_command_template,
        "regression_baseline_ref": baseline,
        "run_command": run_command,
        "blockers": ",".join(blockers),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
    }


def build_product_public_benchmark_contract(*, scorecard_csv: str | Path, root: str | Path | None = None) -> dict[str, Any]:
    root_path = Path(root).resolve() if root is not None else Path(scorecard_csv).resolve().parent
    scorecard_csv_present, scorecard_rows = _read_scorecard_rows(scorecard_csv)
    evidence_by_suite = {_text(row.get("suite_id")): row for row in scorecard_rows}
    rows = [
        _row(
            suite,
            evidence_by_suite.get(_text(suite["suite_id"])),
            scorecard_csv_present=scorecard_csv_present,
            root=root_path,
        )
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
