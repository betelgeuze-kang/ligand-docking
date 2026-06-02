import json
from pathlib import Path

from tools import build_casp17_official_archive_first_baseline_model1_gap_triage as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_builds_model1_gap_triage_packet(tmp_path):
    score_ledger_json = tmp_path / "score_ledger.json"
    rows = []
    for group_id, delta in [
        ("001", "0.000"),
        ("002", "3.000"),
        ("003", "12.000"),
        ("004", "35.000"),
        ("005", "70.000"),
    ]:
        rows.append(
            {
                "target_id": "T9999",
                "group_id": group_id,
                "group_status": "group_score_ready",
                "model1_model_id": f"T9999TS{group_id}_1",
                "model1_metric_status": "metric_ready",
                "model1_gdt_ts_proxy": "10.000",
                "best_top5_model_id": f"T9999TS{group_id}_4",
                "best_top5_model_number": "4",
                "best_top5_metric_status": "metric_ready",
                "best_top5_gdt_ts_proxy": f"{10.0 + float(delta):.3f}",
                "best_minus_model1_gdt_ts_proxy": delta,
                "complete_top5_group": "True",
                "top5_ready_count": 5,
            }
        )
    rows.append({"target_id": "T9999", "group_id": "006", "group_status": "group_score_blocked"})
    _write_json(
        score_ledger_json,
        {
            "summary": {
                "official_archive_first_baseline_score_ledger_status": (
                    "official_archive_first_baseline_score_ledger_ready_baseline_only"
                ),
                "first_baseline_candidate_id": "official_archive_baseline_001",
                "first_competition": "CASP16",
                "first_target_id": "T9999",
                "first_native_pdb_code": "9XYZ",
                "mean_model1_gdt_ts_proxy": "10.000",
                "mean_best_top5_gdt_ts_proxy": "34.000",
                "mean_best_minus_model1_gdt_ts_proxy": "24.000",
                "competitive_proof_eligible": False,
                "strict_blind_intake_policy": "do_not_import_as_internal_prediction",
            },
            "rows": rows,
        },
    )
    args = mod.parse_args(
        [
            "--score-ledger-json",
            str(score_ledger_json),
            "--out-dir",
            str(tmp_path / "triage"),
            "--out-json",
            str(tmp_path / "triage.json"),
            "--out-csv",
            str(tmp_path / "triage.csv"),
            "--out-md",
            str(tmp_path / "TRIAGE.md"),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["official_archive_first_baseline_model1_gap_triage_status"] == (
        "official_archive_first_baseline_model1_gap_triage_ready_baseline_only"
    )
    assert summary["first_target_id"] == "T9999"
    assert summary["group_count"] == 6
    assert summary["ready_group_count"] == 5
    assert summary["blocked_group_count"] == 1
    assert summary["model1_best_group_count"] == 1
    assert summary["top5_improved_group_count"] == 4
    assert summary["small_gap_count"] == 1
    assert summary["medium_gap_count"] == 1
    assert summary["large_gap_count"] == 1
    assert summary["catastrophic_gap_count"] == 1
    assert summary["critical_calibration_case_count"] == 2
    assert summary["model1_best_rate"] == "0.200"
    assert summary["top5_improved_rate"] == "0.800"
    assert summary["first_triage_group_id"] == "005"
    assert summary["first_triage_band"] == "catastrophic_model1_selection_gap"
    assert payload["rows"][0]["triage_action"] == "critical_model1_failure_case_for_accuracy_estimation_training"
    assert (tmp_path / "triage" / "model1_gap_triage.csv").exists()
    assert (tmp_path / "triage" / "top_gap_worklist.csv").exists()
    assert "Claim Boundary" in (tmp_path / "TRIAGE.md").read_text(encoding="utf-8")
