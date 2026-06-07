from __future__ import annotations

import hashlib
import json
from pathlib import Path

from betelgeuze_product.public_benchmark_scorecard import build_public_benchmark_suite_scorecard


def _write_provenance(path: Path, *, suite_id: str, evidence: Path, rows: int = 1) -> None:
    path.write_text(
        json.dumps(
            {
                "summary": {
                    "suite_id": suite_id,
                    "product_engine_result": True,
                    "source_engine": "betelgeuze_product",
                    "result_artifact": str(evidence),
                    "result_artifact_sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
                    "result_row_count": rows,
                }
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
    _write_provenance(provenance, suite_id="pdbbind_casf_pose_affinity", evidence=evidence)

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
