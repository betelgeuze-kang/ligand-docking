from __future__ import annotations

import hashlib
import json
from pathlib import Path

from betelgeuze_product.public_benchmark_scorecard import (
    PDBBIND_CASF_REQUIRED_RESULT_COLUMNS,
    build_public_benchmark_suite_scorecard,
)


def _pdbbind_casf_gold_summary() -> dict[str, object]:
    return {
        "gold_metric_schema_version": "tier_beta_docking_gold_metrics_v1",
        "gold_metric_status": "pass",
        "top1_mean_rmsd_A": 1.2,
        "top5_best_mean_rmsd_A": 0.8,
        "top1_pose_success_rate": 0.6,
        "top5_pose_success_rate": 0.9,
        "ranking_spearman": 0.5,
        "pr_auc": 0.7,
        "topk_hit_rate": 0.8,
        "decoy_rejection_rate": 0.75,
        "baseline_ranking_spearman": 0.1,
        "refine_ranking_spearman_delta": 0.4,
        "refine_improvement_observed": True,
        "heldout_complex_count": 3,
        "chirality_failure_rate": 0.0,
        "tautomer_failure_rate": 0.0,
        "protonation_failure_rate": 0.0,
        "chemistry_evidence_coverage": 1.0,
        "abstention_precision": 0.9,
        "mean_runtime_ms": 12.5,
        "peak_memory_mb": 42.0,
        "subset_identity_sha256": "a" * 64,
        "gold_metric_blockers": [],
        "result_columns": [
            "suite_id",
            "complex_id",
            "pose_id",
            "pose_success",
            "pose_rmsd_A",
            *PDBBIND_CASF_REQUIRED_RESULT_COLUMNS,
        ],
    }


def _write_provenance(
    path: Path,
    *,
    suite_id: str,
    evidence: Path,
    rows: int = 1,
    extra_summary: dict[str, object] | None = None,
) -> None:
    summary = {
        "suite_id": suite_id,
        "product_engine_result": True,
        "source_engine": "betelgeuze_product",
        "result_artifact": str(evidence),
        "result_artifact_sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
        "result_row_count": rows,
    }
    summary.update(extra_summary or {})
    path.write_text(
        json.dumps(
            {
                "summary": summary,
            }
        ),
        encoding="utf-8",
    )


def test_public_benchmark_suite_scorecard_blocks_missing_evidence(tmp_path: Path) -> None:
    payload = build_public_benchmark_suite_scorecard(
        suite_id="dude_z_decoy_smoke",
        primary_metric_value=0.7,
        evidence_artifact=tmp_path / "missing.csv",
        evidence_row_count=10,
        regression_baseline_ref="dude-z:baseline",
        run_command="python3 tools/build_public_benchmark_suite_scorecard.py",
        out_json=tmp_path / "scorecard.json",
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_public_benchmark_suite_scorecard"
    assert "evidence_artifact_missing" in summary["blockers"]
    assert "product_provenance_json_not_declared" in summary["blockers"]
    assert summary["operator_input_artifacts"] == str(tmp_path / "missing.csv")
    assert summary["operator_output_artifacts"] == str(tmp_path / "scorecard.json")
    assert summary["missing_input_artifacts"] == str(tmp_path / "missing.csv")
    assert summary["threshold"] == summary["primary_metric_threshold"]
    assert summary["metric_gap_to_threshold"] > 0
    assert summary["blocker"] == "evidence_artifact_missing,product_provenance_json_not_declared"
    assert payload["scorecard_row"]["status"] == "fail"


def test_public_benchmark_suite_scorecard_passes_with_metric_above_threshold(tmp_path: Path) -> None:
    evidence = tmp_path / "dude_z_results.csv"
    evidence.write_text("target,metric\nadrb2,0.7\n", encoding="utf-8")
    provenance = tmp_path / "dude_z_provenance.json"
    _write_provenance(provenance, suite_id="dude_z_decoy_smoke", evidence=evidence)

    payload = build_public_benchmark_suite_scorecard(
        suite_id="dude_z_decoy_smoke",
        primary_metric_value=0.7,
        evidence_artifact=evidence,
        product_provenance_json=provenance,
        evidence_row_count=1,
        regression_baseline_ref="dude-z:baseline",
        run_command="python3 tools/build_public_benchmark_suite_scorecard.py",
        out_json=tmp_path / "scorecard.json",
    )

    summary = payload["summary"]
    assert summary["status"] == "public_benchmark_suite_scorecard_pass"
    assert summary["primary_metric"] == "ROC_AUC"
    assert summary["primary_metric_threshold"] == 0.6
    assert summary["threshold"] == 0.6
    assert summary["metric_gap_to_threshold"] > 0
    assert summary["blocker"] == ""
    assert summary["missing_input_artifacts"] == ""
    assert summary["product_provenance_json"] == str(provenance)
    assert payload["scorecard_row"]["suite_id"] == "dude_z_decoy_smoke"
    assert payload["scorecard_row"]["status"] == "pass"
    assert payload["scorecard_row"]["product_provenance_json"] == str(provenance)


def test_public_benchmark_suite_scorecard_rejects_metric_name_mismatch(tmp_path: Path) -> None:
    evidence = tmp_path / "results.csv"
    evidence.write_text("metric\n0.8\n", encoding="utf-8")
    provenance = tmp_path / "results_provenance.json"
    _write_provenance(
        provenance,
        suite_id="pdbbind_casf_pose_affinity",
        evidence=evidence,
        extra_summary=_pdbbind_casf_gold_summary(),
    )

    payload = build_public_benchmark_suite_scorecard(
        suite_id="pdbbind_casf_pose_affinity",
        primary_metric_name="ROC_AUC",
        primary_metric_value=0.8,
        evidence_artifact=evidence,
        product_provenance_json=provenance,
        evidence_row_count=1,
        regression_baseline_ref="pdbbind:baseline",
        run_command="cmd",
        out_json=tmp_path / "scorecard.json",
    )

    assert "primary_metric_mismatch" in payload["summary"]["blockers"]


def test_public_benchmark_suite_scorecard_blocks_stale_pdbbind_casf_without_gold_metrics(tmp_path: Path) -> None:
    evidence = tmp_path / "pdbbind_results.csv"
    evidence.write_text("suite_id,complex_id,pose_success\npdbbind_casf_pose_affinity,1abc,1\n", encoding="utf-8")
    provenance = tmp_path / "pdbbind_provenance.json"
    _write_provenance(provenance, suite_id="pdbbind_casf_pose_affinity", evidence=evidence)

    payload = build_public_benchmark_suite_scorecard(
        suite_id="pdbbind_casf_pose_affinity",
        primary_metric_value=0.8,
        evidence_artifact=evidence,
        product_provenance_json=provenance,
        evidence_row_count=1,
        regression_baseline_ref="pdbbind:baseline",
        run_command="python3 tools/build_public_benchmark_suite_scorecard.py",
        out_json=tmp_path / "scorecard.json",
    )

    blockers = payload["summary"]["blockers"]
    assert payload["summary"]["status"] == "blocked_public_benchmark_suite_scorecard"
    assert "pdbbind_casf_gold_metric_schema_missing" in blockers
    assert "pdbbind_casf_gold_metric_status_not_pass" in blockers
    assert "pdbbind_casf_refine_improvement_not_observed" in blockers
    assert any(str(blocker).startswith("pdbbind_casf_result_columns_missing:") for blocker in blockers)


def test_public_benchmark_suite_scorecard_passes_pdbbind_casf_with_full_gold_metrics(tmp_path: Path) -> None:
    evidence = tmp_path / "pdbbind_results.csv"
    evidence.write_text(
        "suite_id,complex_id,pose_id,pose_success,pose_rmsd_A,runtime_ms,peak_memory_mb\n"
        "pdbbind_casf_pose_affinity,1abc,1abc_1,1,0.5,10,20\n",
        encoding="utf-8",
    )
    provenance = tmp_path / "pdbbind_provenance.json"
    _write_provenance(
        provenance,
        suite_id="pdbbind_casf_pose_affinity",
        evidence=evidence,
        extra_summary=_pdbbind_casf_gold_summary(),
    )

    payload = build_public_benchmark_suite_scorecard(
        suite_id="pdbbind_casf_pose_affinity",
        primary_metric_value=0.8,
        evidence_artifact=evidence,
        product_provenance_json=provenance,
        evidence_row_count=1,
        regression_baseline_ref="pdbbind:baseline",
        run_command="python3 tools/build_public_benchmark_suite_scorecard.py",
        out_json=tmp_path / "scorecard.json",
    )

    assert payload["summary"]["status"] == "public_benchmark_suite_scorecard_pass"
    assert payload["summary"]["blockers"] == []
