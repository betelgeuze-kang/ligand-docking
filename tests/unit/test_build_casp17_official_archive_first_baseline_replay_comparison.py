import json
from pathlib import Path

from tools.casp17 import build_casp17_official_archive_first_baseline_replay_comparison as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_builds_baseline_replay_comparison_packet(tmp_path):
    score_ledger_json = tmp_path / "score_ledger.json"
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
                "scored_model_count": 10,
                "ready_model_count": 10,
                "blocked_model_count": 0,
                "mean_model1_gdt_ts_proxy": "50.000",
                "mean_best_top5_gdt_ts_proxy": "70.000",
                "mean_best_minus_model1_gdt_ts_proxy": "20.000",
                "max_gap_group_id": "002",
                "max_best_minus_model1_gdt_ts_proxy": "40.000",
                "competitive_proof_eligible": False,
                "strict_blind_intake_policy": "do_not_import_as_internal_prediction",
            },
            "rows": [
                {
                    "group_id": "001",
                    "group_status": "group_score_ready",
                    "model1_gdt_ts_proxy": "80.000",
                    "best_top5_gdt_ts_proxy": "80.000",
                    "best_minus_model1_gdt_ts_proxy": "0.000",
                },
                {
                    "group_id": "002",
                    "group_status": "group_score_ready",
                    "model1_gdt_ts_proxy": "20.000",
                    "best_top5_gdt_ts_proxy": "60.000",
                    "best_minus_model1_gdt_ts_proxy": "40.000",
                },
            ],
        },
    )
    args = mod.parse_args(
        [
            "--score-ledger-json",
            str(score_ledger_json),
            "--out-dir",
            str(tmp_path / "comparison"),
            "--out-json",
            str(tmp_path / "comparison.json"),
            "--out-csv",
            str(tmp_path / "comparison.csv"),
            "--out-md",
            str(tmp_path / "COMPARISON.md"),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["official_archive_first_baseline_replay_comparison_status"] == (
        "official_archive_first_baseline_replay_comparison_ready_baseline_only"
    )
    assert summary["first_target_id"] == "T9999"
    assert summary["band_count"] == 3
    assert summary["direct_comparable_band_count"] == 0
    assert summary["blocked_band_count"] == 3
    assert summary["model1_best_group_count"] == 1
    assert summary["top5_improved_group_count"] == 1
    assert summary["model1_best_rate"] == "0.500"
    assert summary["top5_improved_rate"] == "0.500"
    assert summary["competitive_proof_eligible"] is False
    assert payload["rows"][0]["band_id"] == "casp15_regular_domain"
    assert payload["rows"][1]["competition"] == "CASP16"
    assert payload["rows"][1]["winner_group"] == "Yang-Server"
    assert payload["rows"][1]["direct_comparison_status"] == (
        "not_directly_comparable_proxy_single_target_not_sum_zscore"
    )
    assert (tmp_path / "comparison" / "winner_band_comparison.csv").exists()
    assert "Claim Boundary" in (tmp_path / "COMPARISON.md").read_text(encoding="utf-8")
