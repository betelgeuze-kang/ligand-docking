from __future__ import annotations

import json
from pathlib import Path

from betelgeuze_cameo.performance import build_cameo_performance_packet
from tools import build_cameo_performance_scorecard as tool


def _handoff(status: str = "cameo_handoff_dry_run_ready") -> dict:
    return {
        "summary": {
            "status": status,
            "target_id": "CAMEO100",
            "native_or_external_accuracy_used": False,
            "outbound_email_enabled": False,
        },
        "rows": [
            {"target_id": "CAMEO100", "candidate_id": "model1", "cameo_model_rank": 1},
            {"target_id": "CAMEO100", "candidate_id": "model2", "cameo_model_rank": 2},
        ],
    }


def test_cameo_performance_pending_without_official_results() -> None:
    payload = build_cameo_performance_packet(_handoff(), [])

    summary = payload["summary"]
    assert summary["status"] == "cameo_performance_pending_official_results"
    assert summary["native_local_accuracy_used"] is False
    assert summary["official_cameo_results_used"] is False
    assert summary["external_state_mutated"] is False
    assert payload["blockers"] == []


def test_cameo_performance_accepts_official_model1_result() -> None:
    payload = build_cameo_performance_packet(
        _handoff(),
        [
            {
                "target_id": "CAMEO100",
                "candidate_id": "model1",
                "cameo_model_rank": 1,
                "result_source_kind": "official_cameo",
                "lddt": 0.72,
                "tm_score": 0.64,
                "rmsd_A": 2.4,
            }
        ],
        thresholds={"min_model1_lddt": 0.7, "min_model1_tm_score": 0.5, "max_model1_rmsd_A": 3.0},
    )

    summary = payload["summary"]
    assert summary["status"] == "cameo_performance_evidence_ready"
    assert summary["threshold_gate_status"] == "pass"
    assert summary["accepted_official_result_count"] == 1
    assert summary["model1_lddt"] == 0.72
    assert payload["rows"][0]["official_cameo_result_used"] is True


def test_cameo_performance_default_thresholds_are_product_grade() -> None:
    payload = build_cameo_performance_packet(
        _handoff(),
        [
            {
                "target_id": "CAMEO100",
                "candidate_id": "model1",
                "cameo_model_rank": 1,
                "result_source_kind": "official_cameo",
                "lddt": 0.4,
                "tm_score": 0.2,
                "rmsd_A": 8.0,
            }
        ],
    )

    assert payload["summary"]["status"] == "cameo_performance_threshold_fail"
    assert payload["thresholds"]["min_model1_lddt"] == 0.70
    assert payload["thresholds"]["min_model1_tm_score"] == 0.50
    assert payload["thresholds"]["max_model1_rmsd_A"] == 5.0
    assert {failure["metric"] for failure in payload["threshold_failures"]} == {"lddt", "tm_score", "rmsd_A"}


def test_cameo_performance_accepts_threshold_policy_packet() -> None:
    payload = build_cameo_performance_packet(
        _handoff(),
        [
            {
                "target_id": "CAMEO100",
                "candidate_id": "model1",
                "cameo_model_rank": 1,
                "result_source_kind": "official_cameo",
                "lddt": 0.72,
                "tm_score": 0.64,
                "rmsd_A": 2.4,
            }
        ],
        threshold_policy_packet={
            "summary": {"profile_name": "product_grade_model1", "threshold_policy_ready": True},
            "thresholds": {"min_model1_lddt": 0.70, "min_model1_tm_score": 0.50, "max_model1_rmsd_A": 5.0},
        },
    )

    assert payload["summary"]["status"] == "cameo_performance_evidence_ready"
    assert payload["summary"]["threshold_policy_ready"] is True
    assert payload["summary"]["threshold_profile_name"] == "product_grade_model1"


def test_cameo_performance_blocks_non_official_result_source() -> None:
    payload = build_cameo_performance_packet(
        _handoff(),
        [
            {
                "target_id": "CAMEO100",
                "candidate_id": "model1",
                "cameo_model_rank": 1,
                "result_source_kind": "local_native",
                "lddt": 0.99,
            }
        ],
    )

    assert payload["summary"]["status"] == "blocked_cameo_performance_scorecard"
    assert any(blocker["code"] == "official_result_row_blocked" for blocker in payload["blockers"])


def test_cameo_performance_records_threshold_failure() -> None:
    payload = build_cameo_performance_packet(
        _handoff(),
        [
            {
                "target_id": "CAMEO100",
                "candidate_id": "model1",
                "cameo_model_rank": 1,
                "result_source_kind": "official_cameo",
                "lddt": 0.4,
            }
        ],
        thresholds={"min_model1_lddt": 0.7},
    )

    assert payload["summary"]["status"] == "cameo_performance_threshold_fail"
    assert payload["summary"]["threshold_gate_status"] == "fail"
    assert payload["threshold_failures"][0]["metric"] == "lddt"


def test_cameo_performance_tool_writes_outputs(tmp_path: Path) -> None:
    handoff_json = tmp_path / "handoff.json"
    results_csv = tmp_path / "results.csv"
    out_json = tmp_path / "scorecard.json"
    out_csv = tmp_path / "scorecard.csv"
    out_md = tmp_path / "scorecard.md"
    handoff_json.write_text(json.dumps(_handoff()) + "\n", encoding="utf-8")
    results_csv.write_text(
        "target_id,candidate_id,cameo_model_rank,result_source_kind,lddt,tm_score,rmsd_A\n"
        "CAMEO100,model1,1,official_cameo,0.72,0.64,2.4\n",
        encoding="utf-8",
    )

    tool.main(
        [
            "--handoff-json",
            str(handoff_json),
            "--results-csv",
            str(results_csv),
            "--min-model1-lddt",
            "0.7",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "cameo_performance_evidence_ready"
    assert out_csv.read_text(encoding="utf-8").startswith("target_id,")
    assert "CAMEO Performance Scorecard" in out_md.read_text(encoding="utf-8")


def test_cameo_performance_tool_writes_blocked_output_for_missing_handoff(tmp_path: Path) -> None:
    out_json = tmp_path / "scorecard.json"
    out_csv = tmp_path / "scorecard.csv"
    out_md = tmp_path / "scorecard.md"

    tool.main(
        [
            "--handoff-json",
            str(tmp_path / "missing_handoff.json"),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    summary = json.loads(out_json.read_text(encoding="utf-8"))["summary"]
    assert summary["status"] == "blocked_cameo_performance_scorecard"
    assert summary["external_state_mutated"] is False
    assert out_csv.read_text(encoding="utf-8") == ""
