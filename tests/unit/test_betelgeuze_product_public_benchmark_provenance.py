from __future__ import annotations

import hashlib
import json
from pathlib import Path

from betelgeuze_product.public_benchmark_provenance import build_public_benchmark_result_provenance


def test_public_benchmark_result_provenance_fingerprints_product_result(tmp_path: Path) -> None:
    result = tmp_path / "results.csv"
    result.write_text("suite_id,target_id,candidate_id,primary_metric_value\ns,T1,L1,0.7\n", encoding="utf-8")
    execution = tmp_path / "execution.json"
    execution.write_text('{"pass": true}\n', encoding="utf-8")

    payload = build_public_benchmark_result_provenance(
        suite_id="dude_z_decoy_smoke",
        result_artifact=result,
        execution_summary_json=execution,
        source_engine="betelgeuze_product",
        min_result_rows=1,
    )

    summary = payload["summary"]
    assert summary["status"] == "public_benchmark_result_provenance_ready"
    assert summary["product_engine_result"] is True
    assert summary["result_artifact_sha256"] == hashlib.sha256(result.read_bytes()).hexdigest()
    assert summary["result_row_count"] == 1
    assert summary["execution_summary_pass"] is True
    assert summary["external_state_mutated"] is False


def test_public_benchmark_result_provenance_carries_gold_metric_summary(tmp_path: Path) -> None:
    result = tmp_path / "results.csv"
    result.write_text("suite_id,target_id,candidate_id,primary_metric_value\ns,T1,L1,0.7\n", encoding="utf-8")
    execution = tmp_path / "execution.json"
    execution.write_text(
        json.dumps(
            {
                "summary": {
                    "pass": True,
                    "gold_metric_schema_version": "tier_beta_docking_gold_metrics_v1",
                    "gold_metric_status": "pass",
                    "top1_mean_rmsd_A": 1.0,
                    "top5_best_mean_rmsd_A": 0.5,
                    "refine_improvement_observed": True,
                    "subset_identity_sha256": "a" * 64,
                }
            }
        ),
        encoding="utf-8",
    )

    payload = build_public_benchmark_result_provenance(
        suite_id="pdbbind_casf_pose_affinity",
        result_artifact=result,
        execution_summary_json=execution,
        source_engine="betelgeuze_product",
        min_result_rows=1,
    )

    summary = payload["summary"]
    assert summary["status"] == "public_benchmark_result_provenance_ready"
    assert summary["gold_metric_schema_version"] == "tier_beta_docking_gold_metrics_v1"
    assert summary["gold_metric_status"] == "pass"
    assert summary["top1_mean_rmsd_A"] == 1.0
    assert summary["refine_improvement_observed"] is True
    assert summary["subset_identity_sha256"] == "a" * 64


def test_public_benchmark_result_provenance_blocks_missing_result(tmp_path: Path) -> None:
    payload = build_public_benchmark_result_provenance(
        suite_id="dude_z_decoy_smoke",
        result_artifact=tmp_path / "missing.csv",
        min_result_rows=1,
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_public_benchmark_result_provenance"
    assert "result_artifact_missing" in summary["blockers"]
    assert "result_rows_below_minimum" in summary["blockers"]
    assert summary["product_engine_result"] is False
